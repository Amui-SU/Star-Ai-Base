"""已禁用的旧接口统一 410 Gone 帮助函数。"""

from fastapi import HTTPException

LEGACY_SCOPED_API_DETAIL = "旧全局接口已禁用，请使用 /knowledge-bases/* 范围化 API。"
LEGACY_AUTH_API_DETAIL = (
    "旧 B 站登录接口已禁用，请使用 /source-bindings/bilibili/qrcode 绑定 B 站账号。"
)
LEGACY_FAVORITES_API_DETAIL = (
    "旧收藏夹接口已禁用，请使用 /source-bindings/{binding_id}/favorites 系列接口。"
)


def raise_legacy_api_gone(detail: str = LEGACY_SCOPED_API_DETAIL) -> None:
    raise HTTPException(status_code=410, detail=detail)
