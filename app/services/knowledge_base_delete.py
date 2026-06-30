"""Deletion helpers for knowledge-base routes."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    KnowledgeBase,
    VideoCache,
    VideoTitleOverride,
)


async def delete_knowledge_base_records(
    db: AsyncSession,
    *,
    knowledge_base: KnowledgeBase,
) -> None:
    knowledge_base_id = knowledge_base.id

    await db.execute(
        IngestionTask.__table__.delete().where(
            IngestionTask.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        FavoriteFolder.__table__.delete().where(
            FavoriteFolder.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        FavoriteVideo.__table__.delete().where(
            FavoriteVideo.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        VideoCache.__table__.delete().where(
            VideoCache.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        VideoTitleOverride.__table__.delete().where(
            VideoTitleOverride.knowledge_base_id == knowledge_base_id
        )
    )
    await db.delete(knowledge_base)
