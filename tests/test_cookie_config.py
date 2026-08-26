import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules["httpx"] = types.SimpleNamespace(Timeout=object, AsyncClient=object)

from crawlers import cookie_config


class CookieConfigTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cookie_config.reset_cookie_cache()
        self.environment = patch.dict(
            os.environ,
            {
                "DOUYIN_COOKIE": "env-cookie",
                "COOKIE_CONFIG_URL": "https://toolbox.example",
                "DOUYIN_COOKIE_CONFIG_TOKEN": "reader-token",
                "COOKIE_REFRESH_INTERVAL_SECONDS": "60",
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        cookie_config.reset_cookie_cache()

    async def test_environment_cookie_is_used_when_central_config_is_missing(self):
        os.environ.pop("DOUYIN_COOKIE_CONFIG_TOKEN", None)
        value = await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
        self.assertEqual(value, "env-cookie")

    async def test_central_cookie_is_cached_until_refresh_deadline(self):
        fetch = AsyncMock(return_value=("central-cookie", 7))
        with patch.object(cookie_config, "_fetch_cookie", fetch):
            first = await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
            second = await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
        self.assertEqual(first, "central-cookie")
        self.assertEqual(second, "central-cookie")
        fetch.assert_awaited_once()

    async def test_first_refresh_failure_falls_back_to_environment(self):
        with patch.object(cookie_config, "_fetch_cookie", AsyncMock(side_effect=RuntimeError("offline"))):
            value = await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
        self.assertEqual(value, "env-cookie")

    async def test_refresh_failure_keeps_last_good_cookie(self):
        with patch.object(cookie_config, "_fetch_cookie", AsyncMock(return_value=("last-good", 3))):
            await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
        cookie_config._cache["douyin"].refresh_at = 0
        os.environ["DOUYIN_COOKIE"] = "new-env-fallback"
        with patch.object(cookie_config, "_fetch_cookie", AsyncMock(side_effect=RuntimeError("offline"))):
            value = await cookie_config.get_cookie("douyin", "DOUYIN_COOKIE")
        self.assertEqual(value, "last-good")


if __name__ == "__main__":
    unittest.main()
