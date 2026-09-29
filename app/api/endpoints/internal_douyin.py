"""Small, authenticated parsing surface for the 51use toolbox."""

import hmac
import logging
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from crawlers.bilibili.media import BilibiliAccessError
from crawlers.hybrid.hybrid_crawler import HybridCrawler
from crawlers.utils.utils import extract_valid_urls

logger = logging.getLogger(__name__)
router = APIRouter()
crawler = HybridCrawler()


class ParseRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


def require_internal_token(token: str | None) -> None:
    expected = os.environ.get("INTERNAL_API_TOKEN", "")
    if not expected:
        logger.error("INTERNAL_API_TOKEN is not configured")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service unavailable")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def extract_supported_url(value: str) -> str:
    url = extract_valid_urls(value)
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing supported link")
    host = (urlparse(url).hostname or "").lower()
    supported = (
        host == "douyin.com" or host.endswith(".douyin.com") or host.endswith(".iesdouyin.com")
        or host == "tiktok.com" or host.endswith(".tiktok.com")
        or host == "bilibili.com" or host.endswith(".bilibili.com") or host == "b23.tv"
    )
    if not supported:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only Douyin, TikTok and Bilibili links are supported")
    return url


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.post("/api/parse")
async def parse_video(payload: ParseRequest, x_internal_token: str | None = Header(default=None)) -> dict:
    """Parse one Douyin, TikTok, or Bilibili link without downloading media."""
    require_internal_token(x_internal_token)
    source_url = extract_supported_url(payload.url)
    try:
        data = await crawler.hybrid_parsing_single_video(source_url, minimal=True)
        return {"ok": True, "data": data}
    except HTTPException:
        raise
    except BilibiliAccessError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bilibili VIP cookie is expired or lacks playback entitlement",
        ) from None
    except Exception as exc:
        # Do not log links, cookies, tokens, or upstream response bodies.
        logger.warning("Video parse failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="video parsing failed") from None
