"""Presenter and display-title helpers for source binding routes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceBinding, SourceBindingResponse, VideoTitleOverride


def normalize_bvid(value: str) -> str:
    bvid = (value or "").strip()
    if not bvid:
        raise HTTPException(status_code=400, detail="bvid cannot be empty")
    return bvid


def normalize_custom_title(value: str | None) -> str | None:
    title = (value or "").strip()
    if not title:
        return None
    if len(title) > 120:
        raise HTTPException(status_code=400, detail="title cannot exceed 120 chars")
    return title


async def get_video_title_overrides(
    db: AsyncSession,
    *,
    workspace_id: int,
    knowledge_base_id: int | None,
    source_binding_id: int,
    bvids: list[str],
) -> dict[str, str]:
    if not knowledge_base_id or not bvids:
        return {}
    result = await db.execute(
        select(VideoTitleOverride)
        .where(VideoTitleOverride.workspace_id == workspace_id)
        .where(VideoTitleOverride.knowledge_base_id == knowledge_base_id)
        .where(VideoTitleOverride.source_binding_id == source_binding_id)
        .where(VideoTitleOverride.bvid.in_(bvids))
        .order_by(VideoTitleOverride.id.desc())
    )
    overrides: dict[str, str] = {}
    for item in result.scalars().all():
        overrides.setdefault(item.bvid, item.custom_title)
    return overrides


def video_with_display_title(video: dict, overrides: dict[str, str]) -> dict:
    bvid = video.get("bvid") or ""
    original_title = video.get("title") or bvid
    custom_title = overrides.get(bvid)
    return {
        **video,
        "title": custom_title or original_title,
        "display_title": custom_title or original_title,
        "original_title": original_title,
        "custom_title": custom_title,
    }


def source_binding_response(binding: SourceBinding) -> SourceBindingResponse:
    return SourceBindingResponse(
        id=binding.id,
        source_type=binding.source_type,
        external_account_id=binding.external_account_id,
        external_account_name=binding.external_account_name,
        external_avatar_url=binding.external_avatar_url,
        status=binding.status,
    )
