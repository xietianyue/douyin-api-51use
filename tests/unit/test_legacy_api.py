"""The 51use compatibility boundary must remain stable across upstream syncs."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request

from dtk.api.routes import legacy
from dtk.api.routes.legacy import legacy_payload, require_internal_token
from dtk.api.routes.schemas import ParseRequest


def test_internal_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "correct-token")

    with pytest.raises(HTTPException) as missing:
        require_internal_token(None)
    with pytest.raises(HTTPException) as wrong:
        require_internal_token("wrong-token")

    assert missing.value.status_code == 401
    assert wrong.value.status_code == 401
    require_internal_token("correct-token")


def test_missing_internal_token_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)

    with pytest.raises(HTTPException) as error:
        require_internal_token("anything")

    assert error.value.status_code == 503


def test_video_result_is_translated_to_the_v4_shape() -> None:
    result = legacy_payload(
        {
            "platform": "douyin",
            "content_id": "7123456789012345678",
            "kind": "video",
            "title": "title",
            "description": "description",
            "created_at": "2026-10-10T00:00:00Z",
            "author": {"uid": "author", "nickname": "creator"},
            "stats": {"play_count": 12},
            "music": {"title": "song", "play_url": "https://cdn.example/music.mp3"},
            "tags": ["tag"],
            "media": {
                "covers": [{"url": "https://cdn.example/cover.jpg", "urls": []}],
                "video": {"url": "https://cdn.example/video.mp4", "urls": []},
                "images": [],
            },
        }
    )

    assert result["type"] == "video"
    assert result["video_id"] == "7123456789012345678"
    assert result["author"]["nickname"] == "creator"
    assert result["video_data"]["nwm_video_url_HQ"].endswith("video.mp4")
    assert result["audio_data"]["nwm_audio_url_HQ"].endswith("music.mp3")
    assert result["cover_data"]["cover"].endswith("cover.jpg")


def test_image_result_is_translated_to_the_v4_shape() -> None:
    result = legacy_payload(
        {
            "platform": "tiktok",
            "content_id": "7123456789012345678",
            "kind": "image_album",
            "title": "album",
            "description": "album",
            "author": {"uid": "author", "nickname": "creator"},
            "stats": {},
            "media": {
                "covers": [],
                "video": None,
                "images": [
                    {"url": "https://cdn.example/1.jpg", "urls": []},
                    {"url": "https://cdn.example/2.jpg", "urls": []},
                ],
            },
        }
    )

    assert result["type"] == "image"
    assert result["image_data"]["no_watermark_image_list"] == [
        "https://cdn.example/1.jpg",
        "https://cdn.example/2.jpg",
    ]
    assert "video_data" not in result


@pytest.mark.asyncio
async def test_legacy_route_wraps_a_finished_v5_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "correct-token")
    captured: dict[str, Any] = {}

    async def finished(*args: Any, **kwargs: Any) -> JSONResponse:
        captured.update(kwargs)
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "platform": "douyin",
                    "content_id": "7123456789012345678",
                    "kind": "video",
                    "title": "title",
                    "description": "description",
                    "author": {"uid": "author", "nickname": "creator"},
                    "stats": {},
                    "media": {
                        "covers": [],
                        "video": {"url": "https://cdn.example/video.mp4"},
                        "images": [],
                    },
                },
                "error": None,
                "meta": {},
            }
        )

    monkeypatch.setattr(legacy.operations, "submit_and_wait", finished)
    request = Request({"type": "http", "method": "POST", "path": "/api/parse", "headers": []})

    result = await legacy.parse_video(
        request,
        ParseRequest(url="https://www.douyin.com/video/7123456789012345678"),
        "correct-token",
    )

    assert result["ok"] is True
    assert result["data"]["video_data"]["nwm_video_url_HQ"].endswith("video.mp4")
    assert captured["endpoint"] == "parse"
    assert captured["params"]["include_raw"] is False


@pytest.mark.asyncio
async def test_legacy_route_turns_an_unfinished_task_into_a_retryable_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "correct-token")

    async def running(*args: Any, **kwargs: Any) -> JSONResponse:
        return JSONResponse({"data": {"state": "running"}}, status_code=202)

    monkeypatch.setattr(legacy.operations, "submit_and_wait", running)
    request = Request({"type": "http", "method": "POST", "path": "/api/parse", "headers": []})

    response = await legacy.parse_video(
        request,
        ParseRequest(url="https://www.douyin.com/video/7123456789012345678"),
        "correct-token",
    )

    assert response.status_code == 504
    assert json.loads(response.body)["detail"] == "video parsing timed out"
