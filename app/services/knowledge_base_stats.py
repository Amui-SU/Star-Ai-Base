"""Statistics helpers for knowledge-base routes."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteFolder, FavoriteVideo, KnowledgeBase


async def build_knowledge_base_stats(
    db: AsyncSession,
    *,
    knowledge_base: KnowledgeBase,
) -> dict:
    folder_rows = await db.execute(
        select(
            FavoriteFolder.id,
            FavoriteFolder.media_id,
            FavoriteFolder.last_sync_at,
            FavoriteFolder.media_count,
        )
        .where(FavoriteFolder.knowledge_base_id == knowledge_base.id)
        .where(FavoriteFolder.last_sync_at.isnot(None))
        .order_by(FavoriteFolder.updated_at.desc())
    )

    folders_data = []
    for row in folder_rows.all():
        folder_id, media_id, last_sync, media_count = row
        count_result = await db.execute(
            select(func.count(func.distinct(FavoriteVideo.bvid))).where(
                FavoriteVideo.folder_id == folder_id
            )
        )
        indexed = count_result.scalar() or 0
        folders_data.append(
            {
                "media_id": media_id,
                "indexed_count": indexed,
                "media_count": media_count,
                "last_sync_at": last_sync.isoformat() if last_sync else None,
            }
        )

    total_result = await db.execute(
        select(func.count(func.distinct(FavoriteVideo.bvid))).where(
            FavoriteVideo.knowledge_base_id == knowledge_base.id
        )
    )
    total_videos = total_result.scalar() or 0

    return {
        "knowledge_base_id": knowledge_base.id,
        "workspace_id": knowledge_base.workspace_id,
        "total_videos": total_videos,
        "folders": folders_data,
        "scoped": True,
    }
