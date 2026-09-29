"""Helpers for validating and normalizing Bilibili API responses."""

from __future__ import annotations

from typing import Any


class BilibiliAccessError(ValueError):
    """The configured Bilibili session cannot access the full media."""


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


def require_bilibili_full_playback(payload: Any) -> dict:
    """Reject PGC preview streams produced by a missing or unauthorized VIP session."""

    data = require_bilibili_data(payload, "bangumi play URL")
    if data.get("is_preview") in (1, True) or data.get("error_code") == -10403:
        raise BilibiliAccessError(
            "Bilibili VIP cookie is expired or lacks playback entitlement"
        )
    return data


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
