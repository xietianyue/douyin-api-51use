import unittest

from crawlers.bilibili.media import extract_bilibili_media, require_bilibili_data


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

    def test_business_error_is_not_treated_as_empty_success(self):
        with self.assertRaisesRegex(ValueError, r"code=-412"):
            require_bilibili_data({"code": -412, "message": "request was banned"}, "video detail")

    def test_missing_media_is_an_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "no playable media"):
            extract_bilibili_media({"code": 0, "data": {"format": "mp4"}})


if __name__ == "__main__":
    unittest.main()
