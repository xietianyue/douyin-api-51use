"""Helpers for validating and normalizing Bilibili API responses."""

from __future__ import annotations

from typing import Any


class BilibiliAccessError(ValueError):
    """The configured Bilibili session cannot access the full media."""


class BilibiliCookieExpiredError(BilibiliAccessError):
    """The configured Cookie does not represent a logged-in Bilibili session."""


class BilibiliVipRequiredError(BilibiliAccessError):
    """The logged-in account does not have an active Bilibili VIP membership."""


class BilibiliPlaybackRestrictedError(BilibiliAccessError):
    """The logged-in VIP account still cannot access the full media."""


def require_bilibili_data(payload: Any, operation: str) -> dict:
    """Return a successful response's data/result object or raise a safe error."""

    if not isinstance(payload, dict):
        raise ValueError(f"Bilibili {operation} returned an invalid response")

    code = payload.get("code")
    if code != 0:
        raise ValueError(f"Bilibili {operation} failed (code={code})")

    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload.get("result")
    if not isinstance(data, dict):
        raise ValueError(f"Bilibili {operation} response is missing data/result")
    return data


def require_bilibili_full_playback(payload: Any, account_payload: Any = None) -> dict:
    """Classify a PGC preview using the Cookie's independent account status."""

    data = require_bilibili_data(payload, "bangumi play URL")
    is_preview = data.get("is_preview") in (1, True) or data.get("error_code") == -10403
    if not is_preview:
        return data

    if not isinstance(account_payload, dict):
        raise BilibiliPlaybackRestrictedError("当前账号无该视频播放权限")

    if account_payload.get("code") == -101:
        raise BilibiliCookieExpiredError("B站 Cookie 已失效，请更新后重试")

    account = require_bilibili_data(account_payload, "account status")
    if account.get("isLogin") is not True:
        raise BilibiliCookieExpiredError("B站 Cookie 已失效，请更新后重试")
    if account.get("vipStatus") not in (1, True):
        raise BilibiliVipRequiredError("该视频需要大会员权限")

    raise BilibiliPlaybackRestrictedError("当前账号无该视频播放权限")


def _first_media_url(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None

    for key in ("url", "baseUrl", "base_url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("backupUrl", "backup_url"):
        values = item.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def extract_bilibili_media(payload: Any) -> tuple[str, str | None]:
    """Extract a playable video URL and an optional separate audio URL.

    Progressive ``durl`` streams already contain audio, so they are preferred.
    DASH is used as a fallback and may require the caller to handle audio
    separately.
    """

    data = require_bilibili_data(payload, "play URL")

    durl = data.get("durl")
    if isinstance(durl, list):
        for item in durl:
            video_url = _first_media_url(item)
            if video_url:
                return video_url, None

    dash = data.get("dash")
    if isinstance(dash, dict):
        video_items = dash.get("video")
        if isinstance(video_items, list):
            for item in video_items:
                video_url = _first_media_url(item)
                if not video_url:
                    continue

                audio_url = None
                audio_items = dash.get("audio")
                if isinstance(audio_items, list):
                    for audio_item in audio_items:
                        audio_url = _first_media_url(audio_item)
                        if audio_url:
                            break
                return video_url, audio_url

    raise ValueError("Bilibili play URL response contains no playable media")
