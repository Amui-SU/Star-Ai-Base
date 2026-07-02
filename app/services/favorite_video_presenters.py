"""Shared presenters for Bilibili favorite video payloads."""

from collections.abc import Sequence
from typing import Any

INVALID_FAVORITE_VIDEO_TITLES = {"已失效视频", "已删除视频"}


def _media_bvid(media: dict[str, Any]) -> Any:
    return media.get("bvid") or media.get("bv_id")


def _upper_name(media: dict[str, Any]) -> Any:
    return (media.get("upper") or {}).get("name")


def _is_invalid_favorite_media(
    media: dict[str, Any],
    *,
    bvid: Any,
    title: Any,
) -> bool:
    return (
        not bvid or media.get("attr", 0) == 9 or title in INVALID_FAVORITE_VIDEO_TITLES
    )


def favorite_video_summary(media: dict[str, Any]) -> dict[str, Any]:
    """Map a paged favorite media payload to the UI video summary shape."""
    return {
        "bvid": _media_bvid(media),
        "title": media.get("title"),
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": _upper_name(media),
        "play_count": (media.get("cnt_info") or {}).get("play"),
        "intro": media.get("intro"),
        "is_selected": True,
    }


def legacy_valid_favorite_video_summary(
    media: dict[str, Any],
) -> dict[str, Any] | None:
    """Map valid legacy favorite media to the legacy all-videos response shape."""
    bvid = _media_bvid(media)
    title = media.get("title", "")
    if _is_invalid_favorite_media(media, bvid=bvid, title=title):
        return None
    return {
        "bvid": bvid,
        "title": title,
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": _upper_name(media),
        "cid": media.get("ugc", {}).get("first_cid") if media.get("ugc") else None,
    }


def source_binding_valid_favorite_video_summary(
    media: dict[str, Any],
) -> dict[str, Any] | None:
    """Map valid source-binding favorite media to the scoped import shape."""
    bvid = _media_bvid(media)
    title = media.get("title", "")
    if _is_invalid_favorite_media(media, bvid=bvid, title=title):
        return None
    return {
        "bvid": bvid,
        "title": title,
        "cover": media.get("cover"),
        "duration": media.get("duration"),
        "owner": _upper_name(media),
        "intro": media.get("intro"),
        "is_selected": True,
    }


def _favorite_resource_id(media: dict[str, Any]) -> Any:
    return media.get("id") or media.get("aid") or media.get("avid")


def favorite_organize_candidate(media: dict[str, Any]) -> dict[str, Any] | None:
    """Map valid favorite media to the legacy organization candidate shape."""
    bvid = _media_bvid(media)
    title = media.get("title") or bvid or ""
    if _is_invalid_favorite_media(media, bvid=bvid, title=title):
        return None

    resource_id = _favorite_resource_id(media)
    if not resource_id:
        return None
    try:
        resource_id = int(resource_id)
    except Exception:
        return None

    resource_type = media.get("type") or 2
    try:
        resource_type = int(resource_type)
    except Exception:
        resource_type = 2

    return {
        "bvid": bvid,
        "title": title,
        "resource_id": resource_id,
        "resource_type": resource_type,
    }


def source_binding_favorite_organization_item(
    media: dict[str, Any],
    *,
    default_folder_title: str,
) -> dict[str, Any] | None:
    """Map valid source-binding media to the organization preview item shape."""
    bvid = _media_bvid(media)
    title = media.get("title") or bvid or ""
    if _is_invalid_favorite_media(media, bvid=bvid, title=title):
        return None
    resource_id = _favorite_resource_id(media)
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


def dedupe_favorite_organization_items(
    items: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep the first organization item for each Bilibili resource pair."""
    seen = set()
    deduped = []
    for item in items:
        key = (item["resource_id"], item["resource_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
