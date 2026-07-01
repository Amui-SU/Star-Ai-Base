"""Favorite folder flows for source binding routes."""

from collections import defaultdict
from collections.abc import Callable, Sequence
from inspect import isawaitable
from typing import Any

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.schemas.content import FavoriteFolderInfo
from app.services.favorite_folders import is_default_favorite_folder
from app.services.source_binding_presenters import (
    get_video_title_overrides as default_get_video_title_overrides,
    video_with_display_title as default_with_display_title,
)
from app.services.source_binding_services import get_bilibili_service_for_binding


async def _resolve_bilibili_service(
    get_service: Callable[..., Any],
    binding_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
) -> Any:
    service = get_service(binding_id, current_user, current_workspace, db)
    if isawaitable(service):
        return await service
    return service


def _favorite_video_summary(media: dict[str, Any]) -> dict[str, Any]:
    return {
        "bvid": media.get("bvid") or media.get("bv_id"),
        "title": media.get("title"),
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": (media.get("upper") or {}).get("name"),
        "play_count": (media.get("cnt_info") or {}).get("play"),
        "intro": media.get("intro"),
        "is_selected": True,
    }


def _valid_favorite_video_summary(media: dict[str, Any]) -> dict[str, Any] | None:
    bvid = media.get("bvid") or media.get("bv_id")
    title = media.get("title", "")
    if not bvid:
        return None
    attr = media.get("attr", 0)
    if attr == 9 or title in ["已失效视频", "已删除视频"]:
        return None
    return {
        "bvid": bvid,
        "title": title,
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": (media.get("upper") or {}).get("name"),
        "intro": media.get("intro"),
        "is_selected": True,
    }


def _organization_item(
    media: dict[str, Any],
    *,
    default_folder_title: str,
) -> dict[str, Any] | None:
    bvid = media.get("bvid") or media.get("bv_id")
    title = media.get("title") or bvid or ""
    if not bvid:
        return None
    attr = media.get("attr", 0)
    if attr == 9 or title in ["已失效视频", "已删除视频"]:
        return None
    resource_id = media.get("id") or media.get("aid") or media.get("avid")
    if not resource_id:
        return None
    return {
        "bvid": bvid,
        "title": title,
        "resource_id": int(resource_id),
        "resource_type": int(media.get("type") or 2),
        "target_folder_id": None,
        "target_folder_title": default_folder_title,
        "reason": "待手动分类",
    }


def _dedupe_organization_items(
    items: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in items:
        key = (item["resource_id"], item["resource_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


async def list_bilibili_favorite_folders(
    binding_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
) -> list[FavoriteFolderInfo]:
    """List Bilibili favorite folders for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        user_info = await bili.get_user_info()
        mid = user_info.get("mid")
        folders = await bili.get_user_favorites(mid=mid)
    finally:
        await bili.close()

    return [
        FavoriteFolderInfo(
            media_id=folder["id"],
            title=folder["title"],
            media_count=folder.get("media_count", 0),
            is_selected=True,
            is_default=is_default_favorite_folder(folder),
        )
        for folder in folders
    ]


async def list_bilibili_favorite_videos(
    binding_id: int,
    media_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    knowledge_base_id: int | None,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
    get_video_title_overrides: Callable[..., Any] = default_get_video_title_overrides,
    with_display_title: Callable[[dict, dict[str, str]], dict] = (
        default_with_display_title
    ),
) -> dict[str, Any]:
    """List paginated Bilibili favorite videos for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        result = await bili.get_favorite_content(media_id, pn=page, ps=page_size)
    finally:
        await bili.close()

    videos = [_favorite_video_summary(media) for media in result.get("medias", [])]
    overrides = await get_video_title_overrides(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=binding_id,
        bvids=[video["bvid"] for video in videos if video.get("bvid")],
    )

    return {
        "folder_info": result.get("info"),
        "videos": [with_display_title(video, overrides) for video in videos],
        "has_more": result.get("has_more", False),
        "page": page,
        "page_size": page_size,
    }


async def list_all_bilibili_favorite_videos(
    binding_id: int,
    media_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    knowledge_base_id: int | None,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
    get_video_title_overrides: Callable[..., Any] = default_get_video_title_overrides,
    with_display_title: Callable[[dict, dict[str, str]], dict] = (
        default_with_display_title
    ),
) -> dict[str, Any]:
    """List all valid Bilibili favorite videos for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        all_videos = await bili.get_all_favorite_videos(media_id)
    finally:
        await bili.close()

    videos = [
        video
        for video in (_valid_favorite_video_summary(media) for media in all_videos)
        if video is not None
    ]
    overrides = await get_video_title_overrides(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=binding_id,
        bvids=[video["bvid"] for video in videos],
    )

    return {
        "total": len(all_videos),
        "valid": len(videos),
        "videos": [with_display_title(video, overrides) for video in videos],
    }


async def preview_bilibili_favorite_organization(
    binding_id: int,
    folder_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
    warning_logger: Callable[[str], None] = logger.warning,
) -> dict[str, Any]:
    """Preview favorite organization suggestions for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        user_info = await bili.get_user_info()
        mid = user_info.get("mid")
        folders = await bili.get_user_favorites(mid=mid)

        default_folder = next(
            (folder for folder in folders if is_default_favorite_folder(folder)),
            None,
        )
        if not default_folder:
            raise HTTPException(status_code=400, detail="未找到默认收藏夹")

        default_folder_id = default_folder.get("id")
        if folder_id and folder_id != default_folder_id:
            warning_logger("传入的默认收藏夹ID不匹配，已使用接口默认收藏夹")

        candidate_folders = [
            folder for folder in folders if folder.get("id") != default_folder_id
        ]
        videos = await bili.get_all_favorite_videos(default_folder_id)
        default_folder_title = default_folder.get("title", "默认收藏夹")
        items = [
            item
            for item in (
                _organization_item(
                    media,
                    default_folder_title=default_folder_title,
                )
                for media in videos
            )
            if item is not None
        ]
        deduped = _dedupe_organization_items(items)

        return {
            "default_folder_id": default_folder_id,
            "default_folder_title": default_folder_title,
            "folders": [
                {
                    "media_id": folder["id"],
                    "title": folder["title"],
                    "media_count": folder.get("media_count", 0),
                    "is_selected": True,
                }
                for folder in candidate_folders
            ],
            "items": deduped,
            "stats": {"total": len(videos), "matched": len(deduped)},
        }
    finally:
        await bili.close()


async def execute_bilibili_favorite_moves(
    binding_id: int,
    *,
    default_folder_id: int,
    moves: Sequence[Any],
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
) -> dict[str, int | str]:
    """Move Bilibili favorite resources for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        move_groups: dict[int, list[str]] = defaultdict(list)
        for item in moves:
            if item.target_folder_id == default_folder_id:
                continue
            move_groups[item.target_folder_id].append(
                f"{item.resource_id}:{item.resource_type}"
            )

        total_moved = 0
        for target_id, resources in move_groups.items():
            await bili.move_favorite_resources(
                src_media_id=default_folder_id,
                tar_media_id=target_id,
                resources=resources,
            )
            total_moved += len(resources)

        return {"message": "移动完成", "moved": total_moved, "groups": len(move_groups)}
    finally:
        await bili.close()


async def clean_invalid_bilibili_favorite_resources(
    binding_id: int,
    folder_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    get_service: Callable[..., Any] = get_bilibili_service_for_binding,
) -> dict[str, Any]:
    """Clean invalid Bilibili favorite resources for a source binding."""
    bili = await _resolve_bilibili_service(
        get_service, binding_id, current_user, current_workspace, db
    )
    try:
        data = await bili.clean_favorite_resources(folder_id)
        return {"ok": True, "data": data}
    finally:
        await bili.close()
