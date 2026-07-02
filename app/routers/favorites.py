"""
Bilibili RAG 知识库系统

收藏夹路由
"""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.content import FavoriteFolderInfo
from app.services.favorite_folders import is_legacy_default_favorite_folder
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.legacy_bilibili_sessions import get_session
from app.services.favorites_route_runtime import (
    list_all_legacy_favorite_videos,
    list_legacy_favorite_folders,
    list_legacy_favorite_videos,
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
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    cookies = session.get("cookies", {})
    user_info = session.get("user_info", {})

    bili = bilibili_service_from_cookies(cookies, BilibiliService)
    try:
        mid = user_info.get("mid") or cookies.get("DedeUserID")
        folders = await bili.get_user_favorites(mid=mid)
        default_folder = next(
            (f for f in folders if is_legacy_default_favorite_folder(f)), None
        )
        if not default_folder:
            raise HTTPException(status_code=400, detail="未找到默认收藏夹")

        default_folder_id = default_folder.get("id")
        if payload.folder_id and payload.folder_id != default_folder_id:
            logger.warning("传入的默认收藏夹ID不匹配，已使用接口默认收藏夹")

        candidate_folders = [f for f in folders if f.get("id") != default_folder_id]

        videos = await bili.get_all_favorite_videos(default_folder_id)

        items_data = []
        for media in videos:
            bvid = media.get("bvid") or media.get("bv_id")
            title = media.get("title") or bvid or ""
            if not bvid:
                continue
            attr = media.get("attr", 0)
            if attr == 9 or title in ["已失效视频", "已删除视频"]:
                continue

            resource_id = media.get("id") or media.get("aid") or media.get("avid")
            if not resource_id:
                continue
            try:
                resource_id = int(resource_id)
            except Exception:
                continue
            resource_type = media.get("type") or 2
            try:
                resource_type = int(resource_type)
            except Exception:
                resource_type = 2
            items_data.append(
                {
                    "bvid": bvid,
                    "title": title,
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                }
            )

        items: List[OrganizePreviewItem] = []
        matched = 0
        for idx, item in enumerate(items_data):
            target_folder_id = None
            target_folder_title = default_folder.get("title", "默认收藏夹")
            reason = "待手动分类"
            items.append(
                OrganizePreviewItem(
                    bvid=item["bvid"],
                    title=item["title"],
                    resource_id=item["resource_id"],
                    resource_type=item["resource_type"],
                    target_folder_id=target_folder_id,
                    target_folder_title=target_folder_title,
                    reason=reason,
                )
            )
        folders_payload = [
            FavoriteFolderInfo(
                media_id=f.get("id"),
                title=f.get("title"),
                media_count=f.get("media_count", 0),
                is_selected=True,
                is_default=False,
            )
            for f in candidate_folders
        ]

        return OrganizePreviewResponse(
            default_folder_id=default_folder_id,
            default_folder_title=default_folder.get("title", "默认收藏夹"),
            folders=folders_payload,
            items=items,
            stats={
                "total": len(items),
                "matched": matched,
                "unmatched": len(items) - matched,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"收藏夹整理预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")
    finally:
        await bili.close()


@router.post("/organize/execute")
async def organize_execute(
    payload: OrganizeExecuteRequest,
    session_id: str = Query(..., description="会话ID"),
):
    """
    执行：根据预览结果批量移动收藏夹内容
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    cookies = session.get("cookies", {})

    bili = bilibili_service_from_cookies(cookies, BilibiliService)
    try:
        move_groups: dict[int, List[str]] = {}
        for item in payload.moves:
            if item.target_folder_id == payload.default_folder_id:
                continue
            resources = move_groups.setdefault(item.target_folder_id, [])
            resources.append(f"{item.resource_id}:{item.resource_type}")

        total_moved = 0
        for target_id, resources in move_groups.items():
            if not resources:
                continue
            await bili.move_favorite_resources(
                src_media_id=payload.default_folder_id,
                tar_media_id=target_id,
                resources=resources,
            )
            total_moved += len(resources)
        return {
            "message": "移动完成",
            "moved": total_moved,
            "groups": len(move_groups),
        }
    except Exception as e:
        logger.error(f"收藏夹整理执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")
    finally:
        await bili.close()


@router.post("/organize/clean-invalid")
async def clean_invalid_resources(
    payload: CleanInvalidRequest,
    session_id: str = Query(..., description="会话ID"),
):
    """
    清理收藏夹失效内容
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    cookies = session.get("cookies", {})

    bili = bilibili_service_from_cookies(cookies, BilibiliService)
    try:
        data = await bili.clean_favorite_resources(payload.folder_id)
        return {"message": "清理完成", "data": data}
    except Exception as e:
        logger.error(f"清理失效内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
    finally:
        await bili.close()
