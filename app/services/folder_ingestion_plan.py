"""Planning helpers for favorite-folder ingestion."""

from collections.abc import Iterable

from app.services.folder_ingestion_content import extract_video_info

INVALID_VIDEO_TITLES = {"已失效视频", "已删除视频"}


def build_video_map(
    videos: Iterable[dict],
    *,
    include_bvids: set[str] | None = None,
    exclude_bvids: set[str] | None = None,
) -> tuple[dict[str, dict], int]:
    video_map: dict[str, dict] = {}
    skipped_invalid = 0
    for media in videos:
        bvid, title, cid = extract_video_info(media)
        if not bvid:
            continue
        if include_bvids is not None and bvid not in include_bvids:
            continue
        if exclude_bvids and bvid in exclude_bvids:
            continue

        if media.get("attr", 0) == 9 or title in INVALID_VIDEO_TITLES:
            skipped_invalid += 1
            continue

        owner = media.get("upper") or {}
        video_map[bvid] = {
            "title": title,
            "cid": cid,
            "intro": media.get("intro"),
            "cover": media.get("cover"),
            "duration": media.get("duration"),
            "owner_name": owner.get("name"),
            "owner_mid": owner.get("mid"),
        }
    return video_map, skipped_invalid


def diff_folder_videos(
    *,
    current_bvids: set[str],
    existing_bvids: set[str],
    partial: bool,
) -> tuple[set[str], set[str]]:
    added = current_bvids - existing_bvids
    removed = set() if partial else existing_bvids - current_bvids
    return added, removed
