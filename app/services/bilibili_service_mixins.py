"""Facade mixins for BilibiliService."""

from typing import Any, Dict, List, Optional

from app.services.bilibili_auth import (
    generate_bilibili_qrcode,
    get_bilibili_user_info,
    poll_bilibili_qrcode_status,
)
from app.services.bilibili_favorites import (
    clean_bilibili_favorite_resources,
    get_all_bilibili_favorite_videos,
    get_bilibili_favorite_content,
    get_bilibili_user_favorites,
    move_bilibili_favorite_resources,
)
from app.services.bilibili_media import (
    download_bilibili_audio_to_file,
    normalize_bilibili_media_url,
    subtitle_text_from_payload,
    subtitle_with_timeline_from_payload,
)
from app.services.bilibili_video import (
    get_bilibili_audio_url,
    get_bilibili_player_info,
    get_bilibili_video_info,
    get_bilibili_video_summary,
)
from app.services.wbi import wbi_signer


class BilibiliAuthMixin:
    async def generate_qrcode(self) -> Dict[str, Any]:
        return await generate_bilibili_qrcode(
            client=self.client,
            passport_url=self.PASSPORT_URL,
            parse_json_response=self._parse_json_response,
        )

    async def poll_qrcode_status(self, qrcode_key: str) -> Dict[str, Any]:
        return await poll_bilibili_qrcode_status(
            client=self.client,
            passport_url=self.PASSPORT_URL,
            parse_json_response=self._parse_json_response,
            qrcode_key=qrcode_key,
        )

    async def get_user_info(self) -> Dict[str, Any]:
        return await get_bilibili_user_info(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
        )


class BilibiliFavoritesMixin:
    async def get_user_favorites(self, mid: int = None) -> List[Dict[str, Any]]:
        if mid is None:
            mid = self.dedeuserid
        return await get_bilibili_user_favorites(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            parse_json_response=self._parse_json_response,
            mid=mid,
        )

    async def get_favorite_content(
        self, media_id: int, pn: int = 1, ps: int = 20
    ) -> Dict[str, Any]:
        return await get_bilibili_favorite_content(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            parse_json_response=self._parse_json_response,
            media_id=media_id,
            pn=pn,
            ps=ps,
        )

    async def get_all_favorite_videos(self, media_id: int) -> List[Dict[str, Any]]:
        return await get_all_bilibili_favorite_videos(
            media_id=media_id,
            load_content=self.get_favorite_content,
        )

    async def move_favorite_resources(
        self,
        src_media_id: int,
        tar_media_id: int,
        resources: List[str],
    ) -> Dict[str, Any]:
        return await move_bilibili_favorite_resources(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bili_jct=self.bili_jct,
            dedeuserid=self.dedeuserid,
            src_media_id=src_media_id,
            tar_media_id=tar_media_id,
            resources=resources,
        )

    async def clean_favorite_resources(self, media_id: int) -> Dict[str, Any]:
        return await clean_bilibili_favorite_resources(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bili_jct=self.bili_jct,
            media_id=media_id,
        )


class BilibiliVideoMixin:
    async def get_video_info(self, bvid: str) -> Dict[str, Any]:
        return await get_bilibili_video_info(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
        )

    async def get_video_summary(
        self, bvid: str, cid: int, up_mid: int = None
    ) -> Dict[str, Any]:
        return await get_bilibili_video_summary(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
            cid=cid,
            up_mid=up_mid,
            wbi_signer=wbi_signer,
        )

    async def get_player_info(
        self, bvid: str, cid: int, aid: int = None
    ) -> Dict[str, Any]:
        return await get_bilibili_player_info(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
            cid=cid,
            aid=aid,
            wbi_signer=wbi_signer,
        )

    async def get_audio_url(self, bvid: str, cid: int) -> Optional[str]:
        return await get_bilibili_audio_url(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
            cid=cid,
            wbi_signer=wbi_signer,
        )


class BilibiliMediaMixin:
    async def download_subtitle(self, subtitle_url: str) -> str:
        response = await self.client.get(normalize_bilibili_media_url(subtitle_url))
        data = response.json()
        return subtitle_text_from_payload(data)

    async def download_subtitle_with_timeline(
        self, subtitle_url: str
    ) -> tuple[str, list[dict]]:
        """
        下载字幕并返回文本和完整时间轴

        Returns:
            (text, timeline) - 文本内容和时间轴数据
        """
        response = await self.client.get(normalize_bilibili_media_url(subtitle_url))
        data = response.json()
        return subtitle_with_timeline_from_payload(data)

    async def download_audio_to_file(self, audio_url: str, file_path: str) -> bool:
        return await download_bilibili_audio_to_file(
            self.client,
            audio_url,
            file_path,
            headers=self.HEADERS,
            cookies=self._get_cookies(),
        )
