"""Bilibili chapter helpers for video note timestamp generation."""

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.services.bilibili import BilibiliService
from app.services.bilibili_multi_part import split_part_video_id
from app.services.content_summary import parse_ai_summary_result
from app.services.source_binding_services import get_bilibili_service_for_binding
from app.services.video_note_ai_text import _append_unique, _clean_text, _coerce_time
from app.services.video_note_presenters import VideoNoteSource

logger = logging.getLogger(__name__)

# 官方章节结果的进程内 TTL 缓存：避免每次点"生成时间戳"都实时调 3 个 B 站接口
_VIEW_POINT_CACHE: dict[str, tuple[float, list[dict]]] = {}
_VIEW_POINT_CACHE_TTL_SECONDS = 3600
_VIEW_POINT_CACHE_MAX_ENTRIES = 128


def _view_point_cache_get(key: str) -> list[dict] | None:
    entry = _VIEW_POINT_CACHE.get(key)
    if entry is None:
        return None
    cached_at, items = entry
    if time.monotonic() - cached_at > _VIEW_POINT_CACHE_TTL_SECONDS:
        _VIEW_POINT_CACHE.pop(key, None)
        return None
    return items


def _view_point_cache_set(key: str, items: list[dict]) -> None:
    if len(_VIEW_POINT_CACHE) >= _VIEW_POINT_CACHE_MAX_ENTRIES:
        oldest_key = min(_VIEW_POINT_CACHE, key=lambda k: _VIEW_POINT_CACHE[k][0])
        _VIEW_POINT_CACHE.pop(oldest_key, None)
    _VIEW_POINT_CACHE[key] = (time.monotonic(), items)


def clear_view_point_timestamp_cache() -> None:
    _VIEW_POINT_CACHE.clear()


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

    # 旧数据 page_number 可能为空，从分P存储ID（bvid_p{n}）兜底解析
    _, id_page = split_part_video_id(source.bvid)
    page_hint = source.page_number or id_page

    target_index = None
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        page_number = _coerce_positive_int(page.get("page"))
        cid = _coerce_positive_int(page.get("cid"))
        if page_hint and page_number == page_hint:
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
    if part_duration is None or part_start_seconds is None:
        return items

    times = [_coerce_positive_int(item.get("time")) or 0 for item in items]
    max_time = max(times)
    min_time = min(times)
    # 判定是否为全片累计秒数：超出当前分P时长，或全部时间都落在当前分P
    # 的累计区间起点之后（P2+ 的分P内秒数应从 0 附近开始）
    is_accumulated = max_time > part_duration or (
        part_start_seconds > 0 and min_time >= part_start_seconds
    )
    if not is_accumulated:
        return items

    normalized: list[dict] = []
    for item in items:
        time_value = _coerce_time(item.get("time"))
        relative_time = time_value - part_start_seconds
        if relative_time < 0 or relative_time > part_duration:
            continue
        normalized.append({**item, "time": relative_time})
    # 换算后全部越界说明数据不属于当前分P，宁可返回空让上层走其他兜底，
    # 也不要回退成错误的累计秒数
    return normalized


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

    real_bvid, _ = split_part_video_id(source.bvid)
    video_info = await service.get_video_info(real_bvid)
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

    # source.bvid 是存储ID（分P时形如 bvid_p2），每个分P独立缓存
    cached = _view_point_cache_get(source.bvid)
    if cached is not None:
        return cached

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
        real_bvid, _ = split_part_video_id(source.bvid)
        player_info = await service.get_player_info(real_bvid, int(cid), aid=aid)
        view_point_items = extract_bilibili_view_point_timestamps(player_info)
        if view_point_items:
            items = _normalize_part_relative_timestamps(
                view_point_items,
                source,
                video_info,
            )
        else:
            summary_payload = await service.get_video_summary(
                real_bvid,
                int(cid),
                up_mid=up_mid,
            )
            items = _normalize_part_relative_timestamps(
                _summary_outline_timestamps(summary_payload),
                source,
                video_info,
            )
        # 只缓存成功查询（含空结果）；失败不缓存以便重试
        _view_point_cache_set(source.bvid, items)
        return items
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
