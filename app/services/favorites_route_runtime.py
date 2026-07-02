"""Runtime helpers for legacy favorite-folder routes."""

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.schemas.content import FavoriteFolderInfo
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.favorite_folders import is_legacy_default_favorite_folder
from app.services.favorite_video_presenters import favorite_organize_candidate
from app.services.favorite_video_presenters import favorite_video_summary
from app.services.favorite_video_presenters import (
    legacy_valid_favorite_video_summary as valid_favorite_video_summary,
)
from app.services.legacy_bilibili_sessions import get_session


async def get_bilibili_service_for_legacy_favorites_session(
    session_id: str,
    *,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    session = await get_session_func(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    cookies = session.get("cookies", {})
    user_info = session.get("user_info", {})
    return service_from_cookies(cookies, service_cls), cookies, user_info


async def list_legacy_favorite_folders(
    session_id: str,
    *,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> list[FavoriteFolderInfo]:
    bili, cookies, user_info = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        mid = user_info.get("mid") or cookies.get("DedeUserID")
        folders = await bili.get_user_favorites(mid=mid)
        return [
            FavoriteFolderInfo(
                media_id=folder["id"],
                title=folder["title"],
                media_count=folder.get("media_count", 0),
                is_selected=True,
                is_default=is_legacy_default_favorite_folder(folder),
            )
            for folder in folders
        ]
    finally:
        await bili.close()


async def list_legacy_favorite_videos(
    media_id: int,
    *,
    session_id: str,
    page: int,
    page_size: int,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> dict[str, Any]:
    bili, _, _ = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        result = await bili.get_favorite_content(media_id, pn=page, ps=page_size)
        return {
            "folder_info": result.get("info"),
            "videos": [
                favorite_video_summary(media) for media in result.get("medias", [])
            ],
            "has_more": result.get("has_more", False),
            "page": page,
            "page_size": page_size,
        }
    finally:
        await bili.close()


async def list_all_legacy_favorite_videos(
    media_id: int,
    *,
    session_id: str,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> dict[str, Any]:
    bili, _, _ = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        all_videos = await bili.get_all_favorite_videos(media_id)
        videos = [
            video
            for video in (valid_favorite_video_summary(media) for media in all_videos)
            if video is not None
        ]
        return {"total": len(videos), "videos": videos}
    finally:
        await bili.close()


async def preview_legacy_favorite_organization(
    *,
    folder_id: int,
    session_id: str,
    preview_response_class: type,
    preview_item_class: type,
    folder_info_class: type = FavoriteFolderInfo,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
    warning_logger: Callable[[str], None] = lambda _message: None,
) -> Any:
    bili, cookies, user_info = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        mid = user_info.get("mid") or cookies.get("DedeUserID")
        folders = await bili.get_user_favorites(mid=mid)
        default_folder = next(
            (folder for folder in folders if is_legacy_default_favorite_folder(folder)),
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
        items_data = [
            item
            for item in (favorite_organize_candidate(media) for media in videos)
            if item is not None
        ]

        items = [
            preview_item_class(
                bvid=item["bvid"],
                title=item["title"],
                resource_id=item["resource_id"],
                resource_type=item["resource_type"],
                target_folder_id=None,
                target_folder_title=default_folder.get("title", "默认收藏夹"),
                reason="待手动分类",
            )
            for item in items_data
        ]
        folders_payload = [
            folder_info_class(
                media_id=folder.get("id"),
                title=folder.get("title"),
                media_count=folder.get("media_count", 0),
                is_selected=True,
                is_default=False,
            )
            for folder in candidate_folders
        ]

        return preview_response_class(
            default_folder_id=default_folder_id,
            default_folder_title=default_folder.get("title", "默认收藏夹"),
            folders=folders_payload,
            items=items,
            stats={
                "total": len(items),
                "matched": 0,
                "unmatched": len(items),
            },
        )
    finally:
        await bili.close()


async def execute_legacy_favorite_organization(
    *,
    default_folder_id: int,
    moves: list[Any],
    session_id: str,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> dict[str, int | str]:
    bili, _, _ = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        move_groups: dict[int, list[str]] = {}
        for item in moves:
            target_folder_id = (
                item.get("target_folder_id")
                if isinstance(item, dict)
                else item.target_folder_id
            )
            if target_folder_id == default_folder_id:
                continue
            resource_id = (
                item.get("resource_id") if isinstance(item, dict) else item.resource_id
            )
            resource_type = (
                item.get("resource_type")
                if isinstance(item, dict)
                else item.resource_type
            )
            resources = move_groups.setdefault(target_folder_id, [])
            resources.append(f"{resource_id}:{resource_type}")

        total_moved = 0
        for target_id, resources in move_groups.items():
            if not resources:
                continue
            await bili.move_favorite_resources(
                src_media_id=default_folder_id,
                tar_media_id=target_id,
                resources=resources,
            )
            total_moved += len(resources)
        return {
            "message": "移动完成",
            "moved": total_moved,
            "groups": len(move_groups),
        }
    finally:
        await bili.close()


async def clean_legacy_favorite_invalid_resources(
    *,
    folder_id: int,
    session_id: str,
    get_session_func: Callable[[str], Any] = get_session,
    service_from_cookies: Callable[..., Any] = bilibili_service_from_cookies,
    service_cls: type = BilibiliService,
) -> dict[str, Any]:
    bili, _, _ = await get_bilibili_service_for_legacy_favorites_session(
        session_id,
        get_session_func=get_session_func,
        service_from_cookies=service_from_cookies,
        service_cls=service_cls,
    )
    try:
        data = await bili.clean_favorite_resources(folder_id)
        return {"message": "清理完成", "data": data}
    finally:
        await bili.close()
