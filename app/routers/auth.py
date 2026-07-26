"""
Bilibili RAG 知识库系统

认证路由 - 旧 B 站扫码登录已禁用，仅保留 410 Gone 提示
"""

from fastapi import APIRouter

from app.services.legacy_api import LEGACY_AUTH_API_DETAIL, raise_legacy_api_gone

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/qrcode")
async def generate_qrcode():
    """生成登录二维码（已禁用）"""
    raise_legacy_api_gone(LEGACY_AUTH_API_DETAIL)


@router.get("/qrcode/poll/{qrcode_key}")
async def poll_qrcode_status(qrcode_key: str):
    """轮询二维码登录状态（已禁用）"""
    raise_legacy_api_gone(LEGACY_AUTH_API_DETAIL)


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """获取会话信息（已禁用）"""
    raise_legacy_api_gone(LEGACY_AUTH_API_DETAIL)


@router.delete("/session/{session_id}")
async def logout(session_id: str):
    """退出登录（已禁用）"""
    raise_legacy_api_gone(LEGACY_AUTH_API_DETAIL)
