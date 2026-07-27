"""Video note presenter and source lookup helpers."""

import math
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteFolder, FavoriteVideo, VideoCache, VideoNote
from app.services.bilibili_multi_part import bilibili_video_url
from app.services.knowledge_base_presenters import nullable_equal


@dataclass(frozen=True)
class VideoNoteSource:
    bvid: str
    cid: int | None
    title: str
    original_title: str
    folder_title: str | None
    owner_name: str | None
    duration: int | None
    pic_url: str | None
    description: str | None
    source_binding_id: int | None
    content: str | None
    outline: list | None
    owner_mid: int | None = None
    # 分P元信息
    page_number: int | None = None
    part_title: str | None = None
    total_parts: int | None = None

    @property
    def url(self) -> str:
        return bilibili_video_url(self.bvid)


def _video_cache_matches_favorite():
    return and_(
        FavoriteVideo.bvid == VideoCache.bvid,
        nullable_equal(FavoriteVideo.workspace_id, VideoCache.workspace_id),
        nullable_equal(
            FavoriteVideo.knowledge_base_id,
            VideoCache.knowledge_base_id,
        ),
        nullable_equal(FavoriteVideo.source_binding_id, VideoCache.source_binding_id),
    )


def _coerce_float(value: Any, *, allow_zero: bool = False) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or (number == 0 and not allow_zero):
        return None
    return number


def _first_present_value(mapping: dict, *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _subtitle_timeline_duration(timeline: Any) -> int | None:
    if not isinstance(timeline, list):
        return None

    max_seconds = 0.0
    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        end = _coerce_float(
            _first_present_value(entry, "to", "end", "end_time", "endTime")
        )
        if end is None:
            start = _coerce_float(
                _first_present_value(entry, "from", "start", "start_time"),
                allow_zero=True,
            )
            duration = _coerce_float(entry.get("duration"))
            if start is not None and duration is not None:
                end = start + duration
        if end is not None:
            max_seconds = max(max_seconds, end)

    if max_seconds <= 0:
        return None
    return int(math.ceil(max_seconds))


def _effective_video_duration(video_cache: VideoCache) -> int | None:
    duration = video_cache.duration
    if (video_cache.total_parts or 0) > 1:
        timeline_duration = _subtitle_timeline_duration(
            video_cache.subtitle_timeline_json
        )
        if timeline_duration and (duration is None or timeline_duration < duration):
            return timeline_duration
    return duration


def _normalized_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags or []:
        text = str(tag).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result


def _block(block_id: str, block_type: str, **values: Any) -> dict:
    return {"id": block_id, "type": block_type, **values}


def _outline_items(outline: list | None) -> list[dict]:
    items: list[dict] = []
    for index, entry in enumerate(outline or []):
        timestamp = int(entry.get("timestamp") or 0)
        title = entry.get("title") or f"片段 {index + 1}"
        items.append({"time": timestamp, "text": title})
        for point in entry.get("points") or []:
            point_text = point.get("content")
            if point_text:
                items.append(
                    {
                        "time": int(point.get("timestamp") or timestamp),
                        "text": point_text,
                    }
                )
    return items


def build_standard_note_blocks(source: VideoNoteSource) -> list[dict]:
    blocks = [
        _block("title", "heading", level=1, text=source.title),
        _block(
            "source",
            "quote",
            text=(
                f"来源：{source.url}"
                + (f"\nUP 主：{source.owner_name}" if source.owner_name else "")
            ),
            source=source.url,
        ),
        _block("ai-summary-title", "heading", level=2, text="AI 摘要"),
        _block("ai-summary", "ai_summary", text=(source.content or "").strip()),
        _block("key-points-title", "heading", level=2, text="关键观点"),
        _block("key-points", "key_points", items=[]),
        _block("timestamp-title", "heading", level=2, text="时间戳提纲"),
        _block(
            "timestamp-outline",
            "timestamp_outline",
            items=_outline_items(source.outline),
        ),
        _block("my-notes-title", "heading", level=2, text="我的笔记"),
        _block("my-notes", "paragraph", text=""),
        _block("questions-title", "heading", level=2, text="问题与待办"),
        _block("questions", "questions", items=[]),
    ]
    return blocks


def note_to_response(note: VideoNote, source: VideoNoteSource | None = None) -> dict:
    return {
        "id": note.id,
        "user_id": note.user_id,
        "workspace_id": note.workspace_id,
        "knowledge_base_id": note.knowledge_base_id,
        "bvid": note.bvid,
        "source_binding_id": note.source_binding_id,
        "title": note.title,
        "template_id": note.template_id,
        "blocks": note.blocks_json or [],
        "tags": _normalized_tags(note.tags_json),
        "summary_status": note.summary_status,
        "summary_generated_at": note.summary_generated_at,
        "export_filename_template": note.export_filename_template,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "video": video_to_response(source) if source else None,
    }


def video_to_response(source: VideoNoteSource) -> dict:
    # 构建分P信息
    parts = None
    if source.total_parts and source.total_parts > 1:
        # 如果是分P视频，构建parts数组
        # 注意：当前只有当前分P的信息，如果需要完整的所有分P，需要额外查询
        parts = [
            {
                "page": source.page_number or 1,
                "cid": source.cid or 0,
                "part": source.part_title or "",
                "duration": source.duration or 0,
            }
        ]

    return {
        "bvid": source.bvid,
        "title": source.title,
        "original_title": source.original_title,
        "display_title": source.title,
        "folder_title": source.folder_title,
        "owner_name": source.owner_name,
        "duration": source.duration,
        "pic_url": source.pic_url,
        "url": source.url,
        "parts": parts,
    }


async def resolve_video_note_source(
    db: AsyncSession,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> VideoNoteSource:
    result = await db.execute(
        select(
            VideoCache,
            FavoriteFolder.title,
            FavoriteVideo.source_binding_id,
        )
        .select_from(FavoriteVideo)
        .join(FavoriteFolder, FavoriteFolder.id == FavoriteVideo.folder_id)
        .join(VideoCache, _video_cache_matches_favorite())
        .where(FavoriteVideo.workspace_id == workspace_id)
        .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
        .where(FavoriteVideo.bvid == bvid)
        .where(VideoCache.is_processed.is_(True))
        .order_by(FavoriteFolder.id.asc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Video not found in knowledge base")

    video_cache, folder_title, source_binding_id = row
    return VideoNoteSource(
        bvid=video_cache.bvid,
        cid=video_cache.cid,
        title=video_cache.title or video_cache.bvid,
        original_title=video_cache.title or video_cache.bvid,
        folder_title=folder_title,
        owner_name=video_cache.owner_name,
        owner_mid=video_cache.owner_mid,
        duration=_effective_video_duration(video_cache),
        pic_url=video_cache.pic_url,
        description=video_cache.description,
        source_binding_id=source_binding_id,
        content=video_cache.content,
        outline=video_cache.outline_json,
        # 读取分P元信息
        page_number=video_cache.page_number,
        part_title=video_cache.part_title,
        total_parts=video_cache.total_parts,
    )


def note_matches_query(
    note: VideoNote | None, source: VideoNoteSource, query: str
) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True
    candidates = [
        source.bvid,
        source.title,
        source.folder_title or "",
        *(note.tags_json if note else []),
    ]
    return any(normalized in str(candidate).lower() for candidate in candidates)


def note_body_matches_query(note: VideoNote | None, query: str) -> bool:
    if note is None:
        return False
    normalized = query.strip().lower()
    if not normalized:
        return True
    return normalized in str(note.blocks_json or "").lower()


async def list_video_note_sources(
    db: AsyncSession,
    *,
    user_id: int,
    workspace_id: int,
    knowledge_base_id: int,
) -> list[tuple[VideoNoteSource, VideoNote | None]]:
    result = await db.execute(
        select(
            VideoCache,
            FavoriteFolder.title,
            FavoriteVideo.source_binding_id,
            VideoNote,
        )
        .select_from(FavoriteVideo)
        .join(FavoriteFolder, FavoriteFolder.id == FavoriteVideo.folder_id)
        .join(VideoCache, _video_cache_matches_favorite())
        .outerjoin(
            VideoNote,
            and_(
                VideoNote.user_id == user_id,
                VideoNote.workspace_id == workspace_id,
                VideoNote.knowledge_base_id == knowledge_base_id,
                VideoNote.bvid == FavoriteVideo.bvid,
            ),
        )
        .where(FavoriteVideo.workspace_id == workspace_id)
        .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
        .where(VideoCache.is_processed.is_(True))
        .order_by(FavoriteFolder.id.asc(), VideoCache.title.asc())
    )

    rows: list[tuple[VideoNoteSource, VideoNote | None]] = []
    seen: set[str] = set()
    for video_cache, folder_title, source_binding_id, note in result.all():
        if video_cache.bvid in seen:
            continue
        seen.add(video_cache.bvid)
        rows.append(
            (
                VideoNoteSource(
                    bvid=video_cache.bvid,
                    cid=video_cache.cid,
                    title=(note.title if note else None)
                    or video_cache.title
                    or video_cache.bvid,
                    original_title=video_cache.title or video_cache.bvid,
                    folder_title=folder_title,
                    owner_name=video_cache.owner_name,
                    owner_mid=video_cache.owner_mid,
                    duration=_effective_video_duration(video_cache),
                    pic_url=video_cache.pic_url,
                    description=video_cache.description,
                    source_binding_id=source_binding_id,
                    content=video_cache.content,
                    outline=video_cache.outline_json,
                    # 读取分P元信息
                    page_number=video_cache.page_number,
                    part_title=video_cache.part_title,
                    total_parts=video_cache.total_parts,
                ),
                note,
            )
        )
    return rows


def list_item_response(source: VideoNoteSource, note: VideoNote | None) -> dict:
    return {
        "bvid": source.bvid,
        "title": source.title,
        "display_title": source.title,
        "folder_title": source.folder_title,
        "note_id": note.id if note else None,
        "has_note": note is not None,
        "last_edited_at": note.updated_at if note else None,
        "summary_status": note.summary_status if note else "not_created",
        "tags": _normalized_tags(note.tags_json if note else []),
    }
