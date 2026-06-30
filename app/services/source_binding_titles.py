"""Video title override helpers for source binding routes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteFolder, FavoriteVideo, VideoTitleOverride


async def update_video_title_override(
    db: AsyncSession,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    source_binding_id: int,
    user_id: int,
    bvid: str,
    custom_title: str | None,
) -> dict:
    membership = await db.execute(
        select(FavoriteVideo.id)
        .join(FavoriteFolder, FavoriteFolder.id == FavoriteVideo.folder_id)
        .where(FavoriteVideo.workspace_id == workspace_id)
        .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
        .where(FavoriteVideo.source_binding_id == source_binding_id)
        .where(FavoriteVideo.bvid == bvid)
        .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Video not found in knowledge base")

    existing_result = await db.execute(
        select(VideoTitleOverride)
        .where(VideoTitleOverride.workspace_id == workspace_id)
        .where(VideoTitleOverride.knowledge_base_id == knowledge_base_id)
        .where(VideoTitleOverride.source_binding_id == source_binding_id)
        .where(VideoTitleOverride.bvid == bvid)
    )
    existing = existing_result.scalar_one_or_none()

    if custom_title is None:
        if existing is not None:
            await db.delete(existing)
            await db.commit()
        return {
            "ok": True,
            "bvid": bvid,
            "custom_title": None,
        }

    if existing is None:
        existing = VideoTitleOverride(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
            bvid=bvid,
            custom_title=custom_title,
            created_by=user_id,
        )
        db.add(existing)
    else:
        existing.custom_title = custom_title
    await db.commit()

    return {
        "ok": True,
        "bvid": bvid,
        "custom_title": custom_title,
    }
