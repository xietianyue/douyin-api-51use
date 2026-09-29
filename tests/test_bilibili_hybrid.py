import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from crawlers.hybrid.hybrid_crawler import HybridCrawler


def video_detail() -> dict:
    return {
        "code": 0,
        "data": {
            "title": "Episode title",
            "pubdate": 1,
            "owner": {"name": "Uploader"},
            "stat": {},
            "pic": "https://media.example/cover.jpg",
            "cid": 41245934569,
        },
    }


class BilibiliHybridTests(unittest.IsolatedAsyncioTestCase):
    async def test_bangumi_episode_uses_pgc_playurl(self):
        bilibili = SimpleNamespace(
            fetch_bangumi_season=AsyncMock(return_value={
                "result": {
                    "episodes": [{
                        "id": 5708511,
                        "bvid": "BV1N8hg6HEam",
                    }],
                },
            }),
            fetch_one_video=AsyncMock(return_value=video_detail()),
            fetch_bangumi_playurl=AsyncMock(return_value={
                "code": 0,
                "result": {
                    "is_preview": 0,
                    "durl": [{"url": "https://media.example/bangumi.mp4"}],
                },
            }),
            fetch_video_playurl=AsyncMock(),
        )
        crawler = HybridCrawler.__new__(HybridCrawler)
        crawler.BilibiliWebCrawler = bilibili

        result = await crawler.hybrid_parsing_single_video(
            "https://www.bilibili.com/bangumi/play/ep5708511",
            minimal=True,
        )

        self.assertEqual(result["video_id"], "BV1N8hg6HEam")
        self.assertEqual(
            result["video_data"]["nwm_video_url_HQ"],
            "https://media.example/bangumi.mp4",
        )
        bilibili.fetch_bangumi_playurl.assert_awaited_once_with(
            "5708511",
            "BV1N8hg6HEam",
            "41245934569",
        )
        bilibili.fetch_video_playurl.assert_not_awaited()

    async def test_regular_video_keeps_wbi_playurl(self):
        bilibili = SimpleNamespace(
            fetch_bangumi_season=AsyncMock(),
            fetch_one_video=AsyncMock(return_value=video_detail()),
            fetch_bangumi_playurl=AsyncMock(),
            fetch_video_playurl=AsyncMock(return_value={
                "code": 0,
                "data": {
                    "durl": [{"url": "https://media.example/video.mp4"}],
                },
            }),
        )
        crawler = HybridCrawler.__new__(HybridCrawler)
        crawler.BilibiliWebCrawler = bilibili

        result = await crawler.hybrid_parsing_single_video(
            "https://www.bilibili.com/video/BV1N8hg6HEam/",
            minimal=True,
        )

        self.assertEqual(
            result["video_data"]["nwm_video_url_HQ"],
            "https://media.example/video.mp4",
        )
        bilibili.fetch_video_playurl.assert_awaited_once_with(
            "BV1N8hg6HEam",
            "41245934569",
        )
        bilibili.fetch_bangumi_playurl.assert_not_awaited()
        bilibili.fetch_bangumi_season.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
