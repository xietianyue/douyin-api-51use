"""Runtime cookie provider backed by the toolbox Worker.

The provider never logs cookie or token values. Existing environment cookies
remain the startup and outage fallback during migration.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)

_TOKEN_ENV = {
    "douyin": "DOUYIN_COOKIE_CONFIG_TOKEN",
    "bilibili": "BILIBILI_COOKIE_CONFIG_TOKEN",
}


@dataclass
class _CachedCookie:
    value: str = ""
    version: int = 0
    refresh_at: float = 0.0


_cache: Dict[str, _CachedCookie] = {}
_locks: Dict[str, asyncio.Lock] = {}


def _refresh_interval() -> int:
    try:
        configured = int(os.environ.get("COOKIE_REFRESH_INTERVAL_SECONDS", "60"))
    except ValueError:
        configured = 60
    return max(15, min(configured, 3600))


def _configuration(platform: str) -> tuple[str, str]:
    base_url = os.environ.get("COOKIE_CONFIG_URL", "").strip().rstrip("/")
    token_env = _TOKEN_ENV.get(platform, f"{platform.upper().replace('-', '_')}_COOKIE_CONFIG_TOKEN")
    token = os.environ.get(token_env, "").strip()
    return base_url, token


async def _fetch_cookie(platform: str, base_url: str, token: str) -> tuple[str, int]:
    url = f"{base_url}/api/internal/cookies/{quote(platform, safe='')}"
    timeout = httpx.Timeout(5.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    cookie = payload.get("cookie") if isinstance(payload, dict) else None
    if not isinstance(cookie, str) or not cookie.strip():
        raise ValueError("central cookie response is missing cookie")
    try:
        version = int(payload.get("version", 0))
    except (TypeError, ValueError):
        version = 0
    return cookie, version


async def get_cookie(platform: str, fallback_env: str, default: str = "") -> str:
    """Return a hot-refreshed cookie, falling back to the last good/env value."""

    fallback = os.environ.get(fallback_env, default)
    base_url, token = _configuration(platform)
    if not base_url or not token:
        return fallback

    now = time.monotonic()
    cached = _cache.get(platform)
    if cached and cached.value and now < cached.refresh_at:
        return cached.value

    lock = _locks.setdefault(platform, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        cached = _cache.get(platform)
        if cached and cached.value and now < cached.refresh_at:
            return cached.value
        try:
            value, version = await _fetch_cookie(platform, base_url, token)
            _cache[platform] = _CachedCookie(
                value=value,
                version=version,
                refresh_at=now + _refresh_interval(),
            )
            return value
        except Exception as error:  # Network/auth/payload errors all use a safe fallback.
            logger.warning(
                "central cookie refresh failed for %s (%s)",
                platform,
                type(error).__name__,
            )
            if cached and cached.value:
                cached.refresh_at = now + min(15, _refresh_interval())
                return cached.value
            return fallback


def reset_cookie_cache() -> None:
    """Clear process-local state; primarily useful for tests."""

    _cache.clear()
    _locks.clear()
