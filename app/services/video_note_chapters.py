"""Bilibili chapter helpers for video note timestamp generation."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.services.bilibili import BilibiliService
from app.services.content_summary import parse_ai_summary_result
from app.services.source_binding_services import get_bilibili_service_for_binding
from app.services.video_note_ai_text import _append_unique, _clean_text, _coerce_time
from app.services.video_note_presenters import VideoNoteSource

logger = logging.getLogger(__name__)


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def extract_bilibili_view_point_timestamps(
    player_info: dict[str, Any] | None,
) -> list[dict]:
    """Normalize Bilibili player view_points into timestamp outline items."""

    if not player_info:
        return []
    values = player_info.get("view_points") or player_info.get("viewPoints")
    if not isinstance(values, list):
        return []

    items: list[dict] = []
    for entry in values:
        if not isinstance(entry, dict):
            continue
        text = _clean_text(
            _first_present(entry, "content", "title", "text"),
            max_length=150,
        )
        if not text:
            continue
        timestamp = _coerce_time(
            _first_present(entry, "from", "start", "time", "timestamp")
        )
        _append_unique(items, text, time=timestamp)
    return items[:24]


def _summary_outline_timestamps(summary_payload: dict[str, Any] | None) -> list[dict]:
    summary = parse_ai_summary_result(summary_payload)
    if not summary:
        return []

    items: list[dict] = []
    for entry in summary.get("outline") or []:
        if not isinstance(entry, dict):
            continue
        timestamp = _coerce_time(entry.get("timestamp"))
        _append_unique(items, entry.get("title"), time=timestamp)
        for point in entry.get("points") or []:
            if not isinstance(point, dict):
                continue
            _append_unique(
                items,
                point.get("content") or point.get("text"),
                time=_coerce_time(point.get("timestamp"), timestamp),
            )
    return items[:20]


def _coerce_positive_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _part_timing_from_video_info(
    video_info: dict[str, Any] | None,
    source: VideoNoteSource,
) -> tuple[int | None, int | None]:
    pages = (video_info or {}).get("pages") or []
    if not isinstance(pages, list):
        return None, source.duration

    target_index = None
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        page_number = _coerce_positive_int(page.get("page"))
        cid = _coerce_positive_int(page.get("cid"))
        if source.page_number and page_number == source.page_number:
            target_index = index
            break
        if source.cid and cid == source.cid:
            target_index = index
            break

    if target_index is None:
        return None, source.duration

    start_seconds = 0
    for page in pages[:target_index]:
        if isinstance(page, dict):
            start_seconds += _coerce_positive_int(page.get("duration")) or 0
    target_page = pages[target_index]
    part_duration = (
        _coerce_positive_int(target_page.get("duration"))
        if isinstance(target_page, dict)
        else None
    )
    return start_seconds, part_duration or source.duration


def _normalize_part_relative_timestamps(
    items: list[dict],
    source: VideoNoteSource,
    video_info: dict[str, Any] | None,
) -> list[dict]:
    if not items or (source.total_parts or 0) <= 1:
        return items

    part_start_seconds, part_duration = _part_timing_from_video_info(
        video_info,
        source,
    )
    if part_duration is None:
        return items

    max_time = max(_coerce_positive_int(item.get("time")) or 0 for item in items)
    if max_time <= part_duration:
        return items
    if part_start_seconds is None:
        return items

    normalized: list[dict] = []
    for item in items:
        time_value = _coerce_time(item.get("time"))
        relative_time = time_value - part_start_seconds
        if relative_time < 0 or relative_time > part_duration:
            continue
        normalized.append({**item, "time": relative_time})
    return normalized or items


async def _resolve_video_identifiers(
    service: BilibiliService,
    source: VideoNoteSource,
) -> tuple[int | None, int | None, int | None, dict[str, Any] | None]:
    cid = source.cid
    aid = None
    up_mid = getattr(source, "owner_mid", None)
    needs_video_info = not cid or (source.total_parts or 0) > 1
    if not needs_video_info:
        return cid, aid, up_mid, None

    video_info = await service.get_video_info(source.bvid)
    cid = cid or video_info.get("cid")
    aid = video_info.get("aid")
    owner = video_info.get("owner") or {}
    up_mid = up_mid or owner.get("mid") or video_info.get("owner_mid")
    return cid, aid, up_mid, video_info


async def _service_for_source(
    db: AsyncSession | None,
    *,
    user: SystemUser | None,
    workspace: Workspace | None,
    source: VideoNoteSource,
    service_class: type[BilibiliService],
) -> BilibiliService:
    if (
        source.source_binding_id
        and db is not None
        and user is not None
        and workspace is not None
    ):
        return await get_bilibili_service_for_binding(
            source.source_binding_id,
            user,
            workspace,
            db,
            service_class=service_class,
        )
    return service_class()


async def fetch_bilibili_view_point_timestamps(
    db: AsyncSession | None,
    *,
    user: SystemUser | None,
    workspace: Workspace | None,
    source: VideoNoteSource,
    service_class: type[BilibiliService] = BilibiliService,
) -> list[dict]:
    """Fetch official Bilibili chapter timestamps for a video source if available."""

    service: BilibiliService | None = None
    try:
        service = await _service_for_source(
            db,
            user=user,
            workspace=workspace,
            source=source,
            service_class=service_class,
        )
        cid, aid, up_mid, video_info = await _resolve_video_identifiers(
            service,
            source,
        )
        if not cid:
            return []
        player_info = await service.get_player_info(source.bvid, int(cid), aid=aid)
        view_point_items = extract_bilibili_view_point_timestamps(player_info)
        if view_point_items:
            return _normalize_part_relative_timestamps(
                view_point_items,
                source,
                video_info,
            )
        summary_payload = await service.get_video_summary(
            source.bvid,
            int(cid),
            up_mid=up_mid,
        )
        return _normalize_part_relative_timestamps(
            _summary_outline_timestamps(summary_payload),
            source,
            video_info,
        )
    except Exception as exc:
        logger.info(
            "Bilibili view_points unavailable for video note %s: %s",
            source.bvid,
            exc,
        )
        return []
    finally:
        if service is not None:
            await service.close()
