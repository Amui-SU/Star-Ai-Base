"""
Bilibili RAG 知识库系统

B站 API 服务模块
"""

import httpx
from typing import Optional, Dict, Any, List, Mapping
from app.services.bilibili_auth import (
    generate_bilibili_qrcode,
    get_bilibili_user_info,
    poll_bilibili_qrcode_status,
)
from app.services.bilibili_cookies import (
    bilibili_service_from_cookies as _bilibili_service_from_cookies,
    normalize_bilibili_cookies,
    service_kwargs_from_cookies,
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
)
from app.services.bilibili_responses import parse_bilibili_json_response
from app.services.bilibili_video import (
    get_bilibili_audio_url,
    get_bilibili_player_info,
    get_bilibili_video_info,
    get_bilibili_video_summary,
)
from app.services.wbi import wbi_signer


_service_kwargs_from_cookies = service_kwargs_from_cookies


class BilibiliService:
    """B站 API 服务封装"""

    BASE_URL = "https://api.bilibili.com"
    PASSPORT_URL = "https://passport.bilibili.com"

    # 通用请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
    }

    def __init__(
        self,
        sessdata: str | None = None,
        bili_jct: str | None = None,
        dedeuserid: str | None = None,
    ):
        """
        初始化 B站服务

        Args:
            sessdata: B站登录后的 SESSDATA cookie
            bili_jct: B站登录后的 bili_jct cookie (csrf token)
            dedeuserid: B站用户 ID
        """
        self.sessdata = sessdata
        self.bili_jct = bili_jct
        self.dedeuserid = dedeuserid
        timeout = httpx.Timeout(12.0, connect=4.0)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers=self.HEADERS,
            trust_env=False,
        )

    @classmethod
    def from_cookies(cls, cookies: Mapping[str, Any] | None) -> "BilibiliService":
        return cls(**service_kwargs_from_cookies(cookies))

    def _get_cookies(self) -> Dict[str, str]:
        """获取 Cookie"""
        cookies = {}
        if self.sessdata:
            cookies["SESSDATA"] = self.sessdata
        if self.bili_jct:
            cookies["bili_jct"] = self.bili_jct
        if self.dedeuserid:
            cookies["DedeUserID"] = self.dedeuserid
        return cookies

    _parse_json_response = staticmethod(parse_bilibili_json_response)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    # ==================== 登录相关 ====================

    async def generate_qrcode(self) -> Dict[str, Any]:
        """
        生成登录二维码

        Returns:
            {
                "qrcode_key": "二维码 key",
                "qrcode_url": "二维码内容 URL",
                "qrcode_image_base64": "二维码图片 base64"
            }
        """
        return await generate_bilibili_qrcode(
            client=self.client,
            passport_url=self.PASSPORT_URL,
            parse_json_response=self._parse_json_response,
        )

    async def poll_qrcode_status(self, qrcode_key: str) -> Dict[str, Any]:
        """
        轮询二维码登录状态

        Args:
            qrcode_key: 二维码 key

        Returns:
            {
                "status": "waiting" | "scanned" | "confirmed" | "expired",
                "message": "状态描述",
                "cookies": {...} (仅在 confirmed 时有值)
            }
        """
        return await poll_bilibili_qrcode_status(
            client=self.client,
            passport_url=self.PASSPORT_URL,
            parse_json_response=self._parse_json_response,
            qrcode_key=qrcode_key,
        )

    async def get_user_info(self) -> Dict[str, Any]:
        """
        获取当前登录用户信息

        Returns:
            用户信息字典
        """
        return await get_bilibili_user_info(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
        )

    # ==================== 收藏夹相关 ====================

    async def get_user_favorites(self, mid: int = None) -> List[Dict[str, Any]]:
        """
        获取用户的所有收藏夹

        Args:
            mid: 用户 ID，不传则使用当前登录用户

        Returns:
            收藏夹列表
        """
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
        """
        获取收藏夹内容

        Args:
            media_id: 收藏夹 ID
            pn: 页码
            ps: 每页数量 (最大20)

        Returns:
            {
                "info": 收藏夹信息,
                "medias": 视频列表,
                "has_more": 是否有更多
            }
        """
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
        """
        获取收藏夹的所有视频

        Args:
            media_id: 收藏夹 ID

        Returns:
            完整视频列表
        """
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
        """
        批量移动收藏夹内容

        Args:
            src_media_id: 源收藏夹 ID
            tar_media_id: 目标收藏夹 ID
            resources: ["avid:type", ...]
        """
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
        """
        清理收藏夹失效内容
        """
        return await clean_bilibili_favorite_resources(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bili_jct=self.bili_jct,
            media_id=media_id,
        )

    # ==================== 视频信息相关 ====================

    async def get_video_info(self, bvid: str) -> Dict[str, Any]:
        """
        获取视频详细信息

        Args:
            bvid: 视频 BV 号

        Returns:
            视频信息字典
        """
        return await get_bilibili_video_info(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
        )

    async def get_video_summary(
        self, bvid: str, cid: int, up_mid: int = None
    ) -> Dict[str, Any]:
        """
        获取视频 AI 摘要

        Args:
            bvid: 视频 BV 号
            cid: 视频 cid
            up_mid: UP主 ID (可选)

        Returns:
            AI 摘要信息
        """
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
        """
        获取播放器信息（包含字幕信息）

        Args:
            bvid: 视频 BV 号
            cid: 视频 cid
            aid: 视频 aid (可选)

        Returns:
            播放器信息
        """
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
        """
        获取音频流 URL（用于 ASR）

        Args:
            bvid: 视频 BV 号
            cid: 视频 cid

        Returns:
            音频 URL（可能为空）
        """
        return await get_bilibili_audio_url(
            client=self.client,
            base_url=self.BASE_URL,
            cookies=self._get_cookies(),
            bvid=bvid,
            cid=cid,
            wbi_signer=wbi_signer,
        )

    async def download_subtitle(self, subtitle_url: str) -> str:
        """
        下载字幕文件

        Args:
            subtitle_url: 字幕 URL

        Returns:
            字幕文本
        """
        response = await self.client.get(normalize_bilibili_media_url(subtitle_url))
        data = response.json()
        return subtitle_text_from_payload(data)

    async def download_audio_to_file(self, audio_url: str, file_path: str) -> bool:
        """
        下载音频流到本地文件（带 Cookie 与 Referer）

        Args:
            audio_url: 音频 URL
            file_path: 本地保存路径

        Returns:
            是否下载成功
        """
        return await download_bilibili_audio_to_file(
            self.client,
            audio_url,
            file_path,
            headers=self.HEADERS,
            cookies=self._get_cookies(),
        )


def _default_bilibili_service_from_cookies(
    cookies: Mapping[str, Any] | None,
    service_cls: type[BilibiliService] = BilibiliService,
) -> BilibiliService:
    return _bilibili_service_from_cookies(cookies, service_cls)


bilibili_service_from_cookies = _default_bilibili_service_from_cookies
