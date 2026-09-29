# ==============================================================================
# Copyright (C) 2021 Evil0ctal
#
# This file is part of the Douyin_TikTok_Download_API project.
#
# This project is licensed under the Apache License 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# 　　　　 　　  ＿＿
# 　　　 　　 ／＞　　フ
# 　　　 　　| 　_　 _ l
# 　 　　 　／` ミ＿xノ
# 　　 　 /　　　 　 |       Feed me Stars ⭐ ️
# 　　　 /　 ヽ　　 ﾉ
# 　 　 │　　|　|　|
# 　／￣|　　 |　|　|
# 　| (￣ヽ＿_ヽ_)__)
# 　＼二つ
# ==============================================================================
#
# Contributor Link:
# - https://github.com/Evil0ctal
#
# ==============================================================================

import asyncio
import re
import httpx

from crawlers.douyin.web.web_crawler import DouyinWebCrawler  # 导入抖音Web爬虫
from crawlers.tiktok.app.app_crawler import TikTokAPPCrawler  # 导入TikTok App爬虫
from crawlers.tiktok.web.utils import AwemeIdFetcher  # 提取TikTok作品ID
from crawlers.bilibili.web.web_crawler import BilibiliWebCrawler  # 导入Bilibili Web爬虫
from crawlers.bilibili.media import (
    BilibiliAccessError,
    extract_bilibili_media,
    require_bilibili_data,
    require_bilibili_full_playback,
)


class HybridCrawler:
    def __init__(self):
        self.DouyinWebCrawler = DouyinWebCrawler()
        self.TikTokAPPCrawler = TikTokAPPCrawler()
        self.BilibiliWebCrawler = BilibiliWebCrawler()

    async def get_bilibili_video_reference(self, url: str) -> tuple[str, str | None]:
        """
        从 Bilibili URL 中提取 BV 号及可选 ep_id，支持短链和番剧链接
        """
        # 如果是 b23.tv 短链，需要重定向获取真实URL
        if "b23.tv" in url:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, follow_redirects=True)
                url = str(response.url)
        
        # 从URL中提取BV号
        bv_pattern = r'(?:video\/|\/)(BV[A-Za-z0-9]+)'
        match = re.search(bv_pattern, url)
        if match:
            return match.group(1), None

        # 番剧/影视链接没有直接携带 BV 号，需先通过 ep_id 查询分集信息。
        ep_match = re.search(r'/bangumi/play/ep(\d+)', url)
        if ep_match:
            ep_id = ep_match.group(1)
            response = await self.BilibiliWebCrawler.fetch_bangumi_season(ep_id)
            result = response.get("result") or {}
            episodes = result.get("episodes") or []
            episode = next(
                (
                    item for item in episodes
                    if str(item.get("id") or item.get("ep_id")) == ep_id
                ),
                None,
            )
            bv_id = (episode or {}).get("bvid")
            if bv_id:
                return bv_id, ep_id
            raise ValueError(f"Cannot resolve Bilibili episode ep{ep_id} to a BV ID")

        raise ValueError(f"Cannot extract BV ID from URL: {url}")

    async def get_bilibili_bv_id(self, url: str) -> str:
        """Backward-compatible helper returning only the resolved BV ID."""

        bv_id, _ = await self.get_bilibili_video_reference(url)
        return bv_id

    async def hybrid_parsing_single_video(self, url: str, minimal: bool = False):
        bilibili_ep_id = None
        # 解析抖音视频/Parse Douyin video
        if "douyin" in url:
            platform = "douyin"
            aweme_id = await self.DouyinWebCrawler.get_aweme_id(url)
            data = await self.DouyinWebCrawler.fetch_one_video(aweme_id)
            data = data.get("aweme_detail")
            # $.aweme_detail.aweme_type
            aweme_type = data.get("aweme_type")
        # 解析TikTok视频/Parse TikTok video
        elif "tiktok" in url:
            platform = "tiktok"
            aweme_id = await AwemeIdFetcher.get_aweme_id(url)

            # 2024-09-14: Switch to TikTokAPPCrawler instead of TikTokWebCrawler
            # data = await self.TikTokWebCrawler.fetch_one_video(aweme_id)
            # data = data.get("itemInfo").get("itemStruct")

            data = await self.TikTokAPPCrawler.fetch_one_video(aweme_id)
            # $.imagePost exists if aweme_type is photo
            aweme_type = data.get("aweme_type")
        # 解析Bilibili视频/Parse Bilibili video
        elif "bilibili" in url or "b23.tv" in url:
            platform = "bilibili"
            aweme_id, bilibili_ep_id = await self.get_bilibili_video_reference(url)
            response = await self.BilibiliWebCrawler.fetch_one_video(aweme_id)
            data = require_bilibili_data(response, "video detail")
            # Bilibili只有视频类型，aweme_type设为0(video)
            aweme_type = 0
        else:
            raise ValueError("hybrid_parsing_single_video: Cannot judge the video source from the URL.")

        # 检查是否需要返回最小数据/Check if minimal data is required
        if not minimal:
            return data

        # 如果是最小数据，处理数据/If it is minimal data, process the data
        url_type_code_dict = {
            # common
            0: 'video',
            # Douyin
            2: 'image',
            4: 'video',
            68: 'image',
            # TikTok
            51: 'video',
            55: 'video',
            58: 'video',
            61: 'video',
            150: 'image'
        }
        # 判断链接类型/Judge link type
        url_type = url_type_code_dict.get(aweme_type, 'video')
        # print(f"url_type: {url_type}")

        """
        以下为(视频||图片)数据处理的四个方法,如果你需要自定义数据处理请在这里修改.
        The following are four methods of (video || image) data processing. 
        If you need to customize data processing, please modify it here.
        """

        """
        创建已知数据字典(索引相同)，稍后使用.update()方法更新数据
        Create a known data dictionary (index the same), 
        and then use the .update() method to update the data
        """

        # 根据平台适配字段映射
        if platform == 'bilibili':
            result_data = {
                'type': url_type,
                'platform': platform,
                'video_id': aweme_id,
                'desc': data.get("title"),  # Bilibili使用title
                'create_time': data.get("pubdate"),  # Bilibili使用pubdate
                'author': data.get("owner"),  # Bilibili使用owner
                'music': None,  # Bilibili没有音乐信息
                'statistics': data.get("stat"),  # Bilibili使用stat
                'cover_data': {},  # 将在各平台处理中填充
                'hashtags': None,  # Bilibili没有hashtags概念
            }
        else:
            result_data = {
                'type': url_type,
                'platform': platform,
                'video_id': aweme_id,  # 统一使用video_id字段，内容可能是aweme_id或bv_id
                'desc': data.get("desc"),
                'create_time': data.get("create_time"),
                'author': data.get("author"),
                'music': data.get("music"),
                'statistics': data.get("statistics"),
                'cover_data': {},  # 将在各平台处理中填充
                'hashtags': data.get('text_extra'),
            }
        # 创建一个空变量，稍后使用.update()方法更新数据/Create an empty variable and use the .update() method to update the data
        api_data = None
        # 判断链接类型并处理数据/Judge link type and process data
        # 抖音数据处理/Douyin data processing
        if platform == 'douyin':
            # 填充封面数据
            result_data['cover_data'] = {
                'cover': data.get("video", {}).get("cover"),
                'origin_cover': data.get("video", {}).get("origin_cover"),
                'dynamic_cover': data.get("video", {}).get("dynamic_cover")
            }
            # 抖音视频数据处理/Douyin video data processing
            if url_type == 'video':
                # 将信息储存在字典中/Store information in a dictionary
                uri = data['video']['play_addr']['uri']
                wm_video_url_HQ = data['video']['play_addr']['url_list'][0]
                wm_video_url = f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={uri}&radio=1080p&line=0"
                nwm_video_url_HQ = wm_video_url_HQ.replace('playwm', 'play')
                nwm_video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
                api_data = {
                    'video_data':
                        {
                            'wm_video_url': wm_video_url,
                            'wm_video_url_HQ': wm_video_url_HQ,
                            'nwm_video_url': nwm_video_url,
                            'nwm_video_url_HQ': nwm_video_url_HQ
                        }
                }
            # 抖音图片数据处理/Douyin image data processing
            elif url_type == 'image':
                # 无水印图片列表/No watermark image list
                no_watermark_image_list = []
                # 有水印图片列表/With watermark image list
                watermark_image_list = []
                # 遍历图片列表/Traverse image list
                for i in data['images']:
                    no_watermark_image_list.append(i['url_list'][0])
                    watermark_image_list.append(i['download_url_list'][0])
                api_data = {
                    'image_data':
                        {
                            'no_watermark_image_list': no_watermark_image_list,
                            'watermark_image_list': watermark_image_list
                        }
                }
        # TikTok数据处理/TikTok data processing
        elif platform == 'tiktok':
            # 填充封面数据
            result_data['cover_data'] = {
                'cover': data.get("video", {}).get("cover"),
                'origin_cover': data.get("video", {}).get("origin_cover"),
                'dynamic_cover': data.get("video", {}).get("dynamic_cover")
            }
            # TikTok视频数据处理/TikTok video data processing
            if url_type == 'video':
                # 将信息储存在字典中/Store information in a dictionary
                # wm_video = data['video']['downloadAddr']
                # wm_video = data['video']['download_addr']['url_list'][0]
                wm_video = (
                    data.get('video', {})
                    .get('download_addr', {})
                    .get('url_list', [None])[0]
                )

                api_data = {
                    'video_data':
                        {
                            'wm_video_url': wm_video,
                            'wm_video_url_HQ': wm_video,
                            # 'nwm_video_url': data['video']['playAddr'],
                            'nwm_video_url': data['video']['play_addr']['url_list'][0],
                            # 'nwm_video_url_HQ': data['video']['bitrateInfo'][0]['PlayAddr']['UrlList'][0]
                            'nwm_video_url_HQ': data['video']['bit_rate'][0]['play_addr']['url_list'][0]
                        }
                }
            # TikTok图片数据处理/TikTok image data processing
            elif url_type == 'image':
                # 无水印图片列表/No watermark image list
                no_watermark_image_list = []
                # 有水印图片列表/With watermark image list
                watermark_image_list = []
                for i in data['image_post_info']['images']:
                    no_watermark_image_list.append(i['display_image']['url_list'][0])
                    watermark_image_list.append(i['owner_watermark_image']['url_list'][0])
                api_data = {
                    'image_data':
                        {
                            'no_watermark_image_list': no_watermark_image_list,
                            'watermark_image_list': watermark_image_list
                        }
                }
        # Bilibili数据处理/Bilibili data processing
        elif platform == 'bilibili':
            # 填充封面数据
            result_data['cover_data'] = {
                'cover': data.get("pic"),  # Bilibili使用pic作为封面
                'origin_cover': data.get("pic"),
                'dynamic_cover': data.get("pic")
            }
            # Bilibili只有视频，直接处理视频数据
            if url_type == 'video':
                # 获取视频播放地址需要额外调用API
                cid = data.get('cid')  # 获取cid
                if cid:
                    if bilibili_ep_id:
                        playurl_data = await self.BilibiliWebCrawler.fetch_bangumi_playurl(
                            bilibili_ep_id,
                            aweme_id,
                            str(cid),
                        )
                        try:
                            require_bilibili_full_playback(playurl_data)
                        except BilibiliAccessError:
                            account_data = await self.BilibiliWebCrawler.fetch_account_status()
                            require_bilibili_full_playback(playurl_data, account_data)
                    else:
                        # 普通投稿视频继续使用 WBI playurl 接口。
                        playurl_data = await self.BilibiliWebCrawler.fetch_video_playurl(
                            aweme_id,
                            str(cid),
                        )
                    # durl 是自带音频的渐进式 MP4；没有 durl 时再使用 DASH 音视频流。
                    video_url, audio_url = extract_bilibili_media(playurl_data)
                    
                    api_data = {
                        'video_data': {
                            'wm_video_url': video_url,
                            'wm_video_url_HQ': video_url,
                            'nwm_video_url': video_url,  # Bilibili没有水印概念
                            'nwm_video_url_HQ': video_url,
                            'audio_url': audio_url,  # Bilibili音视频分离
                            'cid': cid,  # 保存cid供后续使用
                        }
                    }
                else:
                    raise ValueError("Bilibili video detail is missing cid")
        # 更新数据/Update data
        result_data.update(api_data)
        return result_data

    async def main(self):
        # 测试混合解析单一视频接口/Test hybrid parsing single video endpoint
        # url = "https://v.douyin.com/L4FJNR3/"
        # url = "https://www.tiktok.com/@taylorswift/video/7359655005701311786"
        url = "https://www.tiktok.com/@flukegk83/video/7360734489271700753"
        # url = "https://www.tiktok.com/@minecraft/photo/7369296852669205791"
        minimal = True
        result = await self.hybrid_parsing_single_video(url, minimal=minimal)
        print(result)

        # 占位
        pass


if __name__ == '__main__':
    # 实例化混合爬虫/Instantiate hybrid crawler
    hybird_crawler = HybridCrawler()
    # 运行测试代码/Run test code
    asyncio.run(hybird_crawler.main())
