"""Bilibili chapter helpers for video note timestamp generation."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.services.bilibili import BilibiliService
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
            max_length=100,
        )
        if not text:
            continue
        timestamp = _coerce_time(
            _first_present(entry, "from", "start", "time", "timestamp")
        )
        _append_unique(items, text, time=timestamp)
    return items[:20]


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

    if not source.cid:
        return []

    service: BilibiliService | None = None
    try:
        service = await _service_for_source(
            db,
            user=user,
            workspace=workspace,
            source=source,
            service_class=service_class,
        )
        player_info = await service.get_player_info(source.bvid, int(source.cid))
        return extract_bilibili_view_point_timestamps(player_info)
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
