"""
Bilibili RAG 知识库系统

收藏夹路由
"""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.content import FavoriteFolderInfo
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.legacy_bilibili_sessions import get_session
from app.services.favorites_route_runtime import (
    clean_legacy_favorite_invalid_resources,
    execute_legacy_favorite_organization,
    list_all_legacy_favorite_videos,
    list_legacy_favorite_folders,
    list_legacy_favorite_videos,
    preview_legacy_favorite_organization,
)

router = APIRouter(prefix="/favorites", tags=["收藏夹"])


def _get_legacy_favorites_session(session_id: str):
    return get_session(session_id)


def _legacy_favorites_service_from_cookies(cookies: dict, service_cls: type):
    return bilibili_service_from_cookies(cookies, service_cls)


class OrganizePreviewRequest(BaseModel):
    folder_id: int


class OrganizePreviewItem(BaseModel):
    bvid: str
    title: str
    resource_id: int
    resource_type: int
    target_folder_id: Optional[int] = None
    target_folder_title: str
    reason: Optional[str] = None


class OrganizePreviewResponse(BaseModel):
    default_folder_id: int
    default_folder_title: str
    folders: List[FavoriteFolderInfo]
    items: List[OrganizePreviewItem]
    stats: dict


class OrganizeMoveItem(BaseModel):
    resource_id: int
    resource_type: int
    target_folder_id: int


class OrganizeExecuteRequest(BaseModel):
    default_folder_id: int
    moves: List[OrganizeMoveItem]


class CleanInvalidRequest(BaseModel):
    folder_id: int


@router.get("/list", response_model=List[FavoriteFolderInfo])
async def get_favorites_list(session_id: str = Query(..., description="会话ID")):
    """
    获取用户的收藏夹列表
    """
    try:
        return await list_legacy_favorite_folders(
            session_id,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取收藏夹列表失败: {type(e).__name__}: {e!r}")
        raise HTTPException(status_code=500, detail=f"获取收藏夹失败: {str(e)}")


@router.get("/{media_id}/videos")
async def get_favorite_videos(
    media_id: int,
    session_id: str = Query(..., description="会话ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
):
    """
    获取收藏夹中的视频列表
    """
    try:
        return await list_legacy_favorite_videos(
            media_id,
            session_id=session_id,
            page=page,
            page_size=page_size,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取收藏夹视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频失败: {str(e)}")


@router.get("/{media_id}/all-videos")
async def get_all_favorite_videos(
    media_id: int, session_id: str = Query(..., description="会话ID")
):
    """
    获取收藏夹中的所有视频（用于构建知识库）
    """
    try:
        return await list_all_legacy_favorite_videos(
            media_id,
            session_id=session_id,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取所有视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频失败: {str(e)}")


@router.post("/organize/preview", response_model=OrganizePreviewResponse)
async def organize_preview(
    payload: OrganizePreviewRequest,
    session_id: str = Query(..., description="会话ID"),
):
    """
    预览：按已有收藏夹名称对默认收藏夹内容分类
    """
    try:
        return await preview_legacy_favorite_organization(
            folder_id=payload.folder_id,
            session_id=session_id,
            preview_response_class=OrganizePreviewResponse,
            preview_item_class=OrganizePreviewItem,
            folder_info_class=FavoriteFolderInfo,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
            warning_logger=logger.warning,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"收藏夹整理预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


@router.post("/organize/execute")
async def organize_execute(
    payload: OrganizeExecuteRequest,
    session_id: str = Query(..., description="会话ID"),
):
    """
    执行：根据预览结果批量移动收藏夹内容
    """
    try:
        return await execute_legacy_favorite_organization(
            default_folder_id=payload.default_folder_id,
            moves=payload.moves,
            session_id=session_id,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"收藏夹整理执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/organize/clean-invalid")
async def clean_invalid_resources(
    payload: CleanInvalidRequest,
    session_id: str = Query(..., description="会话ID"),
):
    """
    清理收藏夹失效内容
    """
    try:
        return await clean_legacy_favorite_invalid_resources(
            folder_id=payload.folder_id,
            session_id=session_id,
            get_session_func=_get_legacy_favorites_session,
            service_from_cookies=_legacy_favorites_service_from_cookies,
            service_cls=BilibiliService,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理失效内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
