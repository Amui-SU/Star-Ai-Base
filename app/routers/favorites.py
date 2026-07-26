"""
Bilibili RAG 知识库系统

收藏夹路由 - 旧 session_id 驱动接口已禁用，仅保留 410 Gone 提示
"""

from fastapi import APIRouter

from app.services.legacy_api import (
    LEGACY_FAVORITES_API_DETAIL,
    raise_legacy_api_gone,
)

router = APIRouter(prefix="/favorites", tags=["收藏夹"])


@router.get("/list")
async def get_favorites_list():
    """获取用户的收藏夹列表（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)


@router.get("/{media_id}/videos")
async def get_favorite_videos(media_id: int):
    """获取收藏夹中的视频列表（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)


@router.get("/{media_id}/all-videos")
async def get_all_favorite_videos(media_id: int):
    """获取收藏夹中的所有视频（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)


@router.post("/organize/preview")
async def organize_preview():
    """收藏夹整理预览（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)


@router.post("/organize/execute")
async def organize_execute():
    """执行收藏夹整理（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)


@router.post("/organize/clean-invalid")
async def clean_invalid_resources():
    """清理收藏夹失效内容（已禁用）"""
    raise_legacy_api_gone(LEGACY_FAVORITES_API_DETAIL)
