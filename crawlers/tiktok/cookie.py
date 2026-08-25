"""Load TikTok cookies without exposing Docker env-file parsing to raw values."""

import base64
import binascii
import os


def get_tiktok_cookie(default: str = "") -> str:
    """Prefer a Base64-encoded cookie, with the raw variable kept for compatibility."""
    encoded = os.environ.get("TIKTOK_COOKIE_B64", "").strip()
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise RuntimeError("TIKTOK_COOKIE_B64 must contain Base64-encoded UTF-8") from exc
    return os.environ.get("TIKTOK_COOKIE", default)