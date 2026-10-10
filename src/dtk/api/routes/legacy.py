"""Compatibility surface for the existing 51use Cloudflare Worker.

The upstream v5 API is asynchronous and returns the normalized DTK contract.
The existing Worker predates that contract: it calls POST /api/parse with
X-Internal-Token and expects the compact v4 response. Keep that protocol
at this boundary so the rest of v5 can stay upstream-compatible.
"""

from __future__ import annotations

import hmac
import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from dtk.api.deps import Principal
from dtk.api.routes import content, operations
from dtk.api.routes.schemas import ParseRequest
from dtk.core.types import Scope, UserRole

router = APIRouter(tags=["legacy"])

_INTERNAL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000051")
_DEFAULT_WAIT_SECONDS = 55.0
_MAX_WAIT_SECONDS = 60.0


def require_internal_token(token: str | None) -> None:
    """Validate the private Worker-to-API token without leaking its value."""

    expected = os.environ.get("INTERNAL_API_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service unavailable",
        )
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def _wait_seconds() -> float:
    raw = os.environ.get("INTERNAL_API_WAIT_SECONDS", "")
    try:
        value = float(raw) if raw else _DEFAULT_WAIT_SECONDS
    except ValueError:
        value = _DEFAULT_WAIT_SECONDS
    return min(_MAX_WAIT_SECONDS, max(1.0, value))


def _first_url(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    direct = value.get("url")
    if isinstance(direct, str):
        return direct
    mirrors = value.get("urls")
    if isinstance(mirrors, list):
        return next((item for item in mirrors if isinstance(item, str)), "")
    return ""


def legacy_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Translate one v5 Content object into the compact v4 response shape."""

    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
    music = data.get("music") if isinstance(data.get("music"), dict) else {}
    covers = media.get("covers") if isinstance(media.get("covers"), list) else []
    images = media.get("images") if isinstance(media.get("images"), list) else []
    video = media.get("video") if isinstance(media.get("video"), dict) else {}

    video_url = _first_url(video)
    image_urls = [url for item in images if (url := _first_url(item))]
    cover_urls = [url for item in covers if (url := _first_url(item))]
    cover = cover_urls[0] if cover_urls else (image_urls[0] if image_urls else "")
    music_url = music.get("play_url") if isinstance(music.get("play_url"), str) else ""
    kind = str(data.get("kind") or "video")

    result: dict[str, Any] = {
        "type": "image" if kind == "image_album" else "video",
        "platform": str(data.get("platform") or ""),
        "video_id": str(data.get("content_id") or ""),
        "desc": str(data.get("description") or data.get("title") or ""),
        "create_time": data.get("created_at"),
        "author": author,
        "music": music or None,
        "statistics": stats,
        "cover_data": {
            "cover": cover,
            "origin_cover": cover,
            "dynamic_cover": cover_urls[1] if len(cover_urls) > 1 else cover,
        },
        "hashtags": data.get("tags") or [],
    }
    if video_url:
        result["video_data"] = {
            "wm_video_url": video_url,
            "wm_video_url_HQ": video_url,
            "nwm_video_url": video_url,
            "nwm_video_url_HQ": video_url,
        }
    else:
        result["image_data"] = {
            "no_watermark_image_list": image_urls,
            "watermark_image_list": image_urls,
        }
    if music_url:
        result["audio_data"] = {
            "nwm_audio_url": music_url,
            "nwm_audio_url_HQ": music_url,
        }
    return result


def _internal_principal() -> Principal:
    return Principal(
        user_id=_INTERNAL_USER_ID,
        role=UserRole.ADMIN,
        scopes=frozenset(Scope),
        api_key_id=None,
        rate_limit_per_min=None,
    )


@router.post("/api/parse", include_in_schema=False)
async def parse_video(
    request: Request,
    payload: ParseRequest,
    x_internal_token: str | None = Header(default=None),
) -> Any:
    """Parse one Douyin or TikTok link using the v5 worker and v4 wire format."""

    require_internal_token(x_internal_token)
    kind = content.vet_url(payload.url)
    response = await operations.submit_and_wait(
        request,
        _internal_principal(),
        endpoint=operations.Operation.PARSE.value,
        params={"url": kind.url, "include_raw": False, "callback_url": None},
        wait=_wait_seconds(),
    )
    if response.status_code == status.HTTP_202_ACCEPTED:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "video parsing timed out"},
        )
    if response.status_code != status.HTTP_200_OK:
        return response

    envelope = json.loads(response.body)
    data = envelope.get("data") if isinstance(envelope, dict) else None
    if not isinstance(data, dict):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "video parsing failed"},
        )
    return {"ok": True, "data": legacy_payload(data)}


__all__ = ["legacy_payload", "parse_video", "require_internal_token", "router"]
