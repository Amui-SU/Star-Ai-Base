"""
Bilibili RAG 知识库系统

B站 API 服务模块
"""

import httpx
from typing import Any, Dict, Mapping
from app.services.bilibili_cookies import (
    bilibili_service_from_cookies as _bilibili_service_from_cookies,
    normalize_bilibili_cookies,
    service_kwargs_from_cookies,
)
from app.services.bilibili_responses import parse_bilibili_json_response
from app.services.bilibili_service_mixins import (
    BilibiliAuthMixin,
    BilibiliFavoritesMixin,
    BilibiliMediaMixin,
    BilibiliVideoMixin,
)


_service_kwargs_from_cookies = service_kwargs_from_cookies


class BilibiliService(
    BilibiliAuthMixin,
    BilibiliFavoritesMixin,
    BilibiliVideoMixin,
    BilibiliMediaMixin,
):
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


def _default_bilibili_service_from_cookies(
    cookies: Mapping[str, Any] | None,
    service_cls: type[BilibiliService] = BilibiliService,
) -> BilibiliService:
    return _bilibili_service_from_cookies(cookies, service_cls)


bilibili_service_from_cookies = _default_bilibili_service_from_cookies
