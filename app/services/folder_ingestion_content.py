"""Content selection helpers for favorite-folder ingestion."""

from typing import Optional

from app.models import VideoCache
from app.schemas.content import ContentSource, VideoContent


def extract_video_info(media: dict) -> tuple[str, str, Optional[int]]:
    """Extract Bilibili video identifiers from favorite media payloads."""
    bvid = media.get("bvid") or media.get("bv_id")
    title = media.get("title", bvid)
    cid = None
    ugc = media.get("ugc") or {}
    if ugc.get("first_cid"):
        cid = ugc.get("first_cid")
    else:
        cid = media.get("cid") or media.get("id")
    return bvid, title, cid


def is_better_source(new_source: str, old_source: Optional[str]) -> bool:
    source_priority = {
        ContentSource.BASIC_INFO.value: 1,
        ContentSource.AI_SUMMARY.value: 2,
        ContentSource.SUBTITLE.value: 3,
        ContentSource.ASR.value: 4,
    }
    return source_priority.get(new_source, 0) > source_priority.get(old_source or "", 0)


def should_refresh_cache(cache: Optional[VideoCache]) -> bool:
    if not cache:
        return True
    text = (cache.content or "").strip()
    if len(text) < 50:
        return True
    if cache.content_source in (
        None,
        "",
        ContentSource.BASIC_INFO.value,
        ContentSource.AI_SUMMARY.value,
    ):
        return True
    return False


def is_asr_cache_usable(cache: Optional[VideoCache]) -> bool:
    if not cache:
        return False
    if cache.content_source != ContentSource.ASR.value:
        return False
    text = (cache.content or "").strip()
    return len(text) >= 50


def video_content_from_cache(
    cache: Optional[VideoCache], bvid: str, title: str
) -> Optional[VideoContent]:
    if not cache:
        return None
    text = (cache.content or "").strip()
    if len(text) < 10:
        return None
    try:
        source = ContentSource(cache.content_source)
    except Exception:
        source = ContentSource.BASIC_INFO
    return VideoContent(
        bvid=bvid,
        title=title,
        content=text,
        source=source,
        outline=cache.outline_json,
        subtitle_timeline=cache.subtitle_timeline_json,
    )
