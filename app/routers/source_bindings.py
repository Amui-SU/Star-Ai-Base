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
    SystemUser,
    Workspace,
)
from app.schemas.content import FavoriteFolderInfo
from app.schemas.source_bindings import (
    LoginStatusResponse,
    QRCodeResponse,
    SourceBindingResponse,
)
from app.services.legacy_bilibili_sessions import (
    login_sessions,
    QRCODE_SESSION_TTL,
    _set_session,
    _get_session,
)
from app.security import encrypt_text
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
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
from app.services.source_binding_favorites import (
    clean_invalid_bilibili_favorite_resources,
    execute_bilibili_favorite_moves,
    list_all_bilibili_favorite_videos,
    list_bilibili_favorite_folders,
    list_bilibili_favorite_videos,
    preview_bilibili_favorite_organization,
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
    return await list_bilibili_favorite_folders(
        binding_id,
        current_user,
        current_workspace,
        db,
        get_service=_get_bilibili_service_for_binding,
    )


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
    return await list_bilibili_favorite_videos(
        binding_id,
        media_id,
        current_user,
        current_workspace,
        db,
        page=page,
        page_size=page_size,
        knowledge_base_id=knowledge_base_id,
        get_service=_get_bilibili_service_for_binding,
        get_video_title_overrides=_get_video_title_overrides,
        with_display_title=_with_display_title,
    )


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
    return await list_all_bilibili_favorite_videos(
        binding_id,
        media_id,
        current_user,
        current_workspace,
        db,
        knowledge_base_id=knowledge_base_id,
        get_service=_get_bilibili_service_for_binding,
        get_video_title_overrides=_get_video_title_overrides,
        with_display_title=_with_display_title,
    )


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
    return await preview_bilibili_favorite_organization(
        binding_id,
        folder_id,
        current_user,
        current_workspace,
        db,
        get_service=_get_bilibili_service_for_binding,
        warning_logger=logger.warning,
    )


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
    return await execute_bilibili_favorite_moves(
        binding_id,
        default_folder_id=payload.default_folder_id,
        moves=payload.moves,
        current_user=current_user,
        current_workspace=current_workspace,
        db=db,
        get_service=_get_bilibili_service_for_binding,
    )


@router.post("/{binding_id}/favorites/{folder_id}/clean-invalid")
async def clean_invalid_by_binding(
    binding_id: int,
    folder_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """清理收藏夹失效内容（通过绑定获取 B 站凭据）。"""
    return await clean_invalid_bilibili_favorite_resources(
        binding_id,
        folder_id,
        current_user,
        current_workspace,
        db,
        get_service=_get_bilibili_service_for_binding,
    )
