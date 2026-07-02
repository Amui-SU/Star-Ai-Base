"""Runtime helpers for legacy favorite-folder routes."""

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.schemas.content import FavoriteFolderInfo
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.favorite_folders import is_legacy_default_favorite_folder
from app.services.legacy_bilibili_sessions import get_session

INVALID_FAVORITE_VIDEO_TITLES = {"已失效视频", "已删除视频"}


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


def favorite_video_summary(media: dict[str, Any]) -> dict[str, Any]:
    return {
        "bvid": media.get("bvid") or media.get("bv_id"),
        "title": media.get("title"),
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": media.get("upper", {}).get("name"),
        "play_count": media.get("cnt_info", {}).get("play"),
        "intro": media.get("intro"),
        "is_selected": True,
    }


def valid_favorite_video_summary(media: dict[str, Any]) -> dict[str, Any] | None:
    bvid = media.get("bvid") or media.get("bv_id")
    title = media.get("title", "")
    if not bvid:
        return None
    if media.get("attr", 0) == 9 or title in INVALID_FAVORITE_VIDEO_TITLES:
        return None
    return {
        "bvid": bvid,
        "title": title,
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": media.get("upper", {}).get("name"),
        "cid": media.get("ugc", {}).get("first_cid") if media.get("ugc") else None,
    }


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
