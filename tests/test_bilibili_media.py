import unittest

from crawlers.bilibili.media import (
    BilibiliCookieExpiredError,
    BilibiliPlaybackRestrictedError,
    BilibiliVipRequiredError,
    extract_bilibili_media,
    require_bilibili_data,
    require_bilibili_full_playback,
)


class BilibiliMediaTests(unittest.TestCase):
    def test_durl_is_preferred_as_combined_video(self):
        payload = {
            "code": 0,
            "data": {
                "durl": [{"url": "https://media.example/combined.mp4"}],
                "dash": {
                    "video": [{"baseUrl": "https://media.example/video.m4s"}],
                    "audio": [{"baseUrl": "https://media.example/audio.m4s"}],
                },
            },
        }

        video_url, audio_url = extract_bilibili_media(payload)

        self.assertEqual(video_url, "https://media.example/combined.mp4")
        self.assertIsNone(audio_url)

    def test_dash_supports_snake_case_and_backup_urls(self):
        payload = {
            "code": 0,
            "data": {
                "dash": {
                    "video": [{"base_url": "https://media.example/video.m4s"}],
                    "audio": [{"backupUrl": ["https://media.example/audio.m4s"]}],
                }
            },
        }

        video_url, audio_url = extract_bilibili_media(payload)

        self.assertEqual(video_url, "https://media.example/video.m4s")
        self.assertEqual(audio_url, "https://media.example/audio.m4s")

    def test_pgc_result_envelope_is_supported(self):
        payload = {
            "code": 0,
            "result": {
                "is_preview": 0,
                "durl": [{"url": "https://media.example/bangumi.mp4"}],
            },
        }

        require_bilibili_full_playback(payload)
        video_url, audio_url = extract_bilibili_media(payload)

        self.assertEqual(video_url, "https://media.example/bangumi.mp4")
        self.assertIsNone(audio_url)

    def preview_payload(self):
        return {
            "code": 0,
            "result": {
                "is_preview": 1,
                "error_code": -10403,
                "durl": [{"url": "https://media.example/preview.mp4"}],
            },
        }

    def test_pgc_preview_with_expired_cookie_is_classified(self):
        with self.assertRaisesRegex(BilibiliCookieExpiredError, "Cookie 已失效"):
            require_bilibili_full_playback(
                self.preview_payload(),
                {"code": -101, "message": "账号未登录"},
            )

    def test_pgc_preview_for_logged_in_non_vip_account_is_classified(self):
        account = {"code": 0, "data": {"isLogin": True, "vipStatus": 0}}

        with self.assertRaisesRegex(BilibiliVipRequiredError, "需要大会员权限"):
            require_bilibili_full_playback(self.preview_payload(), account)

    def test_pgc_preview_for_active_vip_uses_restricted_prompt(self):
        account = {"code": 0, "data": {"isLogin": True, "vipStatus": 1}}

        with self.assertRaisesRegex(BilibiliPlaybackRestrictedError, "无该视频播放权限"):
            require_bilibili_full_playback(self.preview_payload(), account)

    def test_pgc_preview_without_account_probe_is_not_misclassified(self):
        payload = {
            "code": 0,
            "result": {
                "is_preview": 1,
                "error_code": -10403,
                "durl": [{"url": "https://media.example/preview.mp4"}],
            },
        }

        with self.assertRaisesRegex(BilibiliPlaybackRestrictedError, "无该视频播放权限"):
            require_bilibili_full_playback(payload)

    def test_business_error_is_not_treated_as_empty_success(self):
        with self.assertRaisesRegex(ValueError, r"code=-412"):
            require_bilibili_data({"code": -412, "message": "request was banned"}, "video detail")

    def test_missing_media_is_an_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "no playable media"):
            extract_bilibili_media({"code": 0, "data": {"format": "mp4"}})


if __name__ == "__main__":
    unittest.main()
