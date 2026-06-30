import json
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_workspace
from app.models import (
    SourceBinding,
    SourceCredential,
    SystemUser,
    Workspace,
)
from app.schemas.content import FavoriteFolderInfo
from app.schemas.source_bindings import (
    LoginStatusResponse,
    QRCodeResponse,
    SourceBindingResponse,
)
from app.routers.auth import (
    login_sessions,
    QRCODE_SESSION_TTL,
    _set_session,
    _get_session,
)
from app.security import encrypt_text
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.favorite_folders import is_default_favorite_folder
from app.services.source_binding_presenters import (
    get_video_title_overrides as _get_video_title_overrides,
    normalize_bvid as _normalize_bvid,
    normalize_custom_title as _normalize_custom_title,
    source_binding_response as _response,
    video_with_display_title as _with_display_title,
)
from app.services.source_binding_titles import update_video_title_override
from app.services.source_binding_services import (
    get_bilibili_service_for_binding as _get_bilibili_service_for_binding,
    generate_bilibili_binding_qrcode as _generate_bilibili_binding_qrcode,
    poll_bilibili_binding_qrcode as _poll_bilibili_binding_qrcode,
)
from app.services.source_binding_pending_states import (
    create_pending_state as _create_pending_state,
    delete_pending_state as _delete_pending_state,
    get_pending_state as _get_pending_state,
)

router = APIRouter(prefix="/source-bindings", tags=["source-bindings"])


class VideoTitleUpdateRequest(BaseModel):
    bvid: str
    title: str | None = None
    knowledge_base_id: int


@router.get("", response_model=list[SourceBindingResponse])
async def list_bindings(
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> list[SourceBindingResponse]:
    result = await db.execute(
        select(SourceBinding)
        .where(SourceBinding.user_id == current_user.id)
        .where(SourceBinding.workspace_id == current_workspace.id)
        .order_by(SourceBinding.id.desc())
    )
    return [_response(binding) for binding in result.scalars().all()]


@router.delete("/{binding_id}")
async def revoke_binding(
    binding_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    binding = await db.get(SourceBinding, binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
    ):
        raise HTTPException(status_code=404, detail="内容源绑定不存在")

    binding.status = "revoked"
    await db.commit()
    return {"ok": True}


@router.get("/bilibili/qrcode", response_model=QRCodeResponse)
async def generate_bilibili_binding_qrcode(
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QRCodeResponse:
    return await _generate_bilibili_binding_qrcode(
        current_user,
        db,
        service_class=BilibiliService,
        set_session=_set_session,
        create_pending_state=_create_pending_state,
        qrcode_session_ttl=QRCODE_SESSION_TTL,
        warning_logger=logger.warning,
    )


@router.get("/bilibili/qrcode/poll/{qrcode_key}", response_model=LoginStatusResponse)
async def poll_bilibili_binding_qrcode(
    qrcode_key: str,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> LoginStatusResponse:
    return await _poll_bilibili_binding_qrcode(
        qrcode_key,
        current_user,
        current_workspace,
        db,
        service_class=BilibiliService,
        service_from_cookies=bilibili_service_from_cookies,
        get_session=_get_session,
        login_sessions=login_sessions,
        get_pending_state=_get_pending_state,
        delete_pending_state=_delete_pending_state,
        encrypt_payload=encrypt_text,
        warning_logger=logger.warning,
    )


# ── 收藏夹接口（通过 source_binding_id 驱动）──


@router.get("/{binding_id}/favorites", response_model=List[FavoriteFolderInfo])
async def list_favorites_by_binding(
    binding_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> List[FavoriteFolderInfo]:
    """通过内容源绑定获取 B 站收藏夹列表。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        # 从 B站Cookie 获取 mid
        user_info = await bili.get_user_info()
        mid = user_info.get("mid")
        folders = await bili.get_user_favorites(mid=mid)
    finally:
        await bili.close()

    return [
        FavoriteFolderInfo(
            media_id=f["id"],
            title=f["title"],
            media_count=f.get("media_count", 0),
            is_selected=True,
            is_default=is_default_favorite_folder(f),
        )
        for f in folders
    ]


@router.get("/{binding_id}/favorites/{media_id}/videos")
async def list_favorite_videos_by_binding(
    binding_id: int,
    media_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
    knowledge_base_id: int | None = Query(None),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """通过内容源绑定获取收藏夹视频列表（分页）。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        result = await bili.get_favorite_content(media_id, pn=page, ps=page_size)
    finally:
        await bili.close()

    videos = []
    for media in result.get("medias", []):
        videos.append(
            {
                "bvid": media.get("bvid") or media.get("bv_id"),
                "title": media.get("title"),
                "cover": media.get("cover"),
                "duration": media.get("duration"),
                "owner": (media.get("upper") or {}).get("name"),
                "play_count": (media.get("cnt_info") or {}).get("play"),
                "intro": media.get("intro"),
                "is_selected": True,
            }
        )

    overrides = await _get_video_title_overrides(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=binding_id,
        bvids=[video["bvid"] for video in videos if video.get("bvid")],
    )

    return {
        "folder_info": result.get("info"),
        "videos": [_with_display_title(video, overrides) for video in videos],
        "has_more": result.get("has_more", False),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{binding_id}/favorites/{media_id}/all-videos")
async def list_all_favorite_videos_by_binding(
    binding_id: int,
    media_id: int,
    knowledge_base_id: int | None = Query(None),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """通过内容源绑定获取收藏夹全部视频（用于构建知识库）。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        all_videos = await bili.get_all_favorite_videos(media_id)
    finally:
        await bili.close()

    videos = []
    for media in all_videos:
        bvid = media.get("bvid") or media.get("bv_id")
        title = media.get("title", "")
        if not bvid:
            continue
        attr = media.get("attr", 0)
        if attr == 9 or title in ["已失效视频", "已删除视频"]:
            continue
        videos.append(
            {
                "bvid": bvid,
                "title": title,
                "cover": media.get("cover"),
                "duration": media.get("duration"),
                "owner": (media.get("upper") or {}).get("name"),
                "intro": media.get("intro"),
                "is_selected": True,
            }
        )

    overrides = await _get_video_title_overrides(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=binding_id,
        bvids=[video["bvid"] for video in videos],
    )

    return {
        "total": len(all_videos),
        "valid": len(videos),
        "videos": [_with_display_title(video, overrides) for video in videos],
    }


@router.put("/{binding_id}/videos/title")
async def update_video_title_by_binding(
    binding_id: int,
    payload: VideoTitleUpdateRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict:
    binding = await db.get(SourceBinding, binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="Source binding not found")

    bvid = _normalize_bvid(payload.bvid)
    custom_title = _normalize_custom_title(payload.title)

    return await update_video_title_override(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=payload.knowledge_base_id,
        source_binding_id=binding.id,
        user_id=current_user.id,
        bvid=bvid,
        custom_title=custom_title,
    )


@router.get("/{binding_id}/favorites/organize-preview")
async def organize_preview_by_binding(
    binding_id: int,
    folder_id: int = Query(..., description="默认收藏夹 ID"),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """预览收藏夹整理建议（通过绑定获取 B 站数据）。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        user_info = await bili.get_user_info()
        mid = user_info.get("mid")
        folders = await bili.get_user_favorites(mid=mid)

        default_folder = next(
            (f for f in folders if is_default_favorite_folder(f)),
            None,
        )
        if not default_folder:
            raise HTTPException(status_code=400, detail="未找到默认收藏夹")

        default_folder_id = default_folder.get("id")
        if folder_id and folder_id != default_folder_id:
            logger.warning("传入的默认收藏夹ID不匹配，已使用接口默认收藏夹")

        candidate_folders = [f for f in folders if f.get("id") != default_folder_id]
        videos = await bili.get_all_favorite_videos(default_folder_id)

        items = []
        for media in videos:
            bvid = media.get("bvid") or media.get("bv_id")
            title = media.get("title") or bvid or ""
            if not bvid:
                continue
            attr = media.get("attr", 0)
            if attr == 9 or title in ["已失效视频", "已删除视频"]:
                continue
            rid = media.get("id") or media.get("aid") or media.get("avid")
            if not rid:
                continue
            items.append(
                {
                    "bvid": bvid,
                    "title": title,
                    "resource_id": int(rid),
                    "resource_type": int(media.get("type") or 2),
                    "target_folder_id": None,
                    "target_folder_title": default_folder.get("title", "默认收藏夹"),
                    "reason": "待手动分类",
                }
            )

        # 去重：同一个资源只保留一条
        seen = set()
        deduped = []
        for item in items:
            key = (item["resource_id"], item["resource_type"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return {
            "default_folder_id": default_folder_id,
            "default_folder_title": default_folder.get("title", "默认收藏夹"),
            "folders": [
                {
                    "media_id": f["id"],
                    "title": f["title"],
                    "media_count": f.get("media_count", 0),
                    "is_selected": True,
                }
                for f in candidate_folders
            ],
            "items": deduped,
            "stats": {"total": len(videos), "matched": len(deduped)},
        }
    finally:
        await bili.close()


class OrganizeMoveItem(BaseModel):
    resource_id: int
    resource_type: int
    target_folder_id: int


class OrganizeExecuteRequest(BaseModel):
    default_folder_id: int
    moves: list[OrganizeMoveItem]


@router.post("/{binding_id}/favorites/organize-execute")
async def organize_execute_by_binding(
    payload: OrganizeExecuteRequest,
    binding_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """执行收藏夹内容移动（通过绑定获取 B 站凭据）。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        move_groups: dict[int, list[str]] = defaultdict(list)
        for item in payload.moves:
            if item.target_folder_id == payload.default_folder_id:
                continue
            move_groups[item.target_folder_id].append(
                f"{item.resource_id}:{item.resource_type}"
            )

        total_moved = 0
        for target_id, resources in move_groups.items():
            await bili.move_favorite_resources(
                src_media_id=payload.default_folder_id,
                tar_media_id=target_id,
                resources=resources,
            )
            total_moved += len(resources)

        return {"message": "移动完成", "moved": total_moved, "groups": len(move_groups)}
    finally:
        await bili.close()


@router.post("/{binding_id}/favorites/{folder_id}/clean-invalid")
async def clean_invalid_by_binding(
    binding_id: int,
    folder_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """清理收藏夹失效内容（通过绑定获取 B 站凭据）。"""
    bili = await _get_bilibili_service_for_binding(
        binding_id, current_user, current_workspace, db
    )
    try:
        data = await bili.clean_favorite_resources(folder_id)
        return {"ok": True, "data": data}
    finally:
        await bili.close()
