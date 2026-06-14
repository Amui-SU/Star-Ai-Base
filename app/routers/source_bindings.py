import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_workspace
from app.models import (
    FavoriteFolderInfo,
    LoginStatusResponse,
    QRCodeResponse,
    SourceBinding,
    SourceBindingResponse,
    SourceCredential,
    SystemUser,
    Workspace,
)
from app.routers.auth import (
    login_sessions,
    QRCODE_SESSION_TTL,
    _set_session,
    _get_session,
)
from app.security import decrypt_text, encrypt_text
from app.services.bilibili import BilibiliService

router = APIRouter(prefix="/source-bindings", tags=["source-bindings"])


def _response(binding: SourceBinding) -> SourceBindingResponse:
    return SourceBindingResponse(
        id=binding.id,
        source_type=binding.source_type,
        external_account_id=binding.external_account_id,
        external_account_name=binding.external_account_name,
        external_avatar_url=binding.external_avatar_url,
        status=binding.status,
    )


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
) -> QRCodeResponse:
    bili = BilibiliService()
    try:
        result = await bili.generate_qrcode()
    finally:
        await bili.close()

    _set_session(
        result["qrcode_key"],
        {
            "status": "waiting",
            "purpose": "source_binding",
            "user_id": current_user.id,
        },
        QRCODE_SESSION_TTL,
    )
    return QRCodeResponse(
        qrcode_key=result["qrcode_key"],
        qrcode_url=result["qrcode_url"],
        qrcode_image_base64=result["qrcode_image_base64"],
    )


@router.get("/bilibili/qrcode/poll/{qrcode_key}", response_model=LoginStatusResponse)
async def poll_bilibili_binding_qrcode(
    qrcode_key: str,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> LoginStatusResponse:
    pending = _get_session(qrcode_key)
    if (
        not pending
        or pending.get("purpose") != "source_binding"
        or pending.get("user_id") != current_user.id
    ):
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")

    bili = BilibiliService()
    try:
        result = await bili.poll_qrcode_status(qrcode_key)
    finally:
        await bili.close()

    response = LoginStatusResponse(
        status=result["status"],
        message=result["message"],
    )
    if result["status"] != "confirmed":
        return response

    cookies = result.get("cookies", {})
    bili_auth = BilibiliService(
        sessdata=cookies.get("SESSDATA"),
        bili_jct=cookies.get("bili_jct"),
        dedeuserid=cookies.get("DedeUserID"),
    )
    try:
        user_info = await bili_auth.get_user_info()
    finally:
        await bili_auth.close()

    external_id = str(user_info.get("mid") or cookies.get("DedeUserID") or "")
    if not external_id:
        raise HTTPException(status_code=502, detail="B 站账号信息缺少用户 ID")

    binding = SourceBinding(
        user_id=current_user.id,
        workspace_id=current_workspace.id,
        source_type="bilibili",
        external_account_id=external_id,
        external_account_name=user_info.get("uname"),
        external_avatar_url=user_info.get("face"),
        status="active",
        last_verified_at=datetime.now(timezone.utc),
    )
    db.add(binding)
    await db.flush()

    credential_payload = {
        "SESSDATA": cookies.get("SESSDATA"),
        "bili_jct": cookies.get("bili_jct"),
        "DedeUserID": cookies.get("DedeUserID"),
    }
    db.add(
        SourceCredential(
            user_id=current_user.id,
            source_binding_id=binding.id,
            encrypted_payload=encrypt_text(
                json.dumps(credential_payload, ensure_ascii=False)
            ),
        )
    )
    await db.commit()

    login_sessions.pop(qrcode_key, None)
    response_mid = int(external_id) if external_id.isdigit() else external_id
    response.user_info = {
        "mid": response_mid,
        "uname": binding.external_account_name,
        "face": binding.external_avatar_url,
    }
    response.session_id = str(binding.id)
    return response


# ── 收藏夹接口（通过 source_binding_id 驱动）──


async def _get_bilibili_service_for_binding(
    binding_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
) -> BilibiliService:
    """从绑定 ID 解析凭据，返回已认证的 BilibiliService 实例。"""
    # 验证绑定归属
    binding = await db.get(SourceBinding, binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="内容源绑定不存在或已失效")

    # 获取最新凭据
    cred_result = await db.execute(
        select(SourceCredential)
        .where(SourceCredential.source_binding_id == binding_id)
        .where(SourceCredential.revoked_at.is_(None))
        .order_by(SourceCredential.id.desc())
    )
    credential = cred_result.scalars().first()
    if credential is None:
        raise HTTPException(status_code=400, detail="内容源凭据不存在或已失效")

    try:
        payload = json.loads(decrypt_text(credential.encrypted_payload))
    except Exception:
        raise HTTPException(status_code=500, detail="凭据解密失败")

    return BilibiliService(
        sessdata=payload.get("SESSDATA"),
        bili_jct=payload.get("bili_jct"),
        dedeuserid=payload.get("DedeUserID"),
    )


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
            is_default=(
                f.get("is_default")
                or f.get("type") == 1
                or f.get("fav_state") == 1
                or (f.get("title") or "").strip() == "默认收藏夹"
            ),
        )
        for f in folders
    ]


@router.get("/{binding_id}/favorites/{media_id}/videos")
async def list_favorite_videos_by_binding(
    binding_id: int,
    media_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
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

    return {
        "folder_info": result.get("info"),
        "videos": videos,
        "has_more": result.get("has_more", False),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{binding_id}/favorites/{media_id}/all-videos")
async def list_all_favorite_videos_by_binding(
    binding_id: int,
    media_id: int,
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

    return {
        "total": len(all_videos),
        "valid": len(videos),
        "videos": videos,
    }


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
            (
                f
                for f in folders
                if (
                    f.get("is_default")
                    or f.get("type") == 1
                    or f.get("fav_state") == 1
                    or (f.get("title") or "").strip() == "默认收藏夹"
                )
            ),
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
