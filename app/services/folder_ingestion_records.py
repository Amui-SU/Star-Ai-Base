"""Database and vector record helpers for favorite-folder ingestion."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteFolder, VideoCache
from app.services.rag import RAGService


def has_cache_scope(
    workspace_id: Optional[int],
    knowledge_base_id: Optional[int],
) -> bool:
    return workspace_id is not None and knowledge_base_id is not None


def _apply_scope_filters(
    stmt,
    model,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
):
    if has_cache_scope(workspace_id, knowledge_base_id):
        return (
            stmt.where(model.workspace_id == workspace_id)
            .where(model.knowledge_base_id == knowledge_base_id)
            .where(
                model.source_binding_id.is_(None)
                if source_binding_id is None
                else model.source_binding_id == source_binding_id
            )
        )
    return stmt.where(model.workspace_id.is_(None)).where(
        model.knowledge_base_id.is_(None)
    )


async def get_or_create_folder(
    db: AsyncSession,
    session_id: str,
    media_id: int,
    title: Optional[str] = None,
    media_count: Optional[int] = None,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> FavoriteFolder:
    """Get or create a favorite-folder database record."""
    stmt = select(FavoriteFolder).where(
        FavoriteFolder.session_id == session_id,
        FavoriteFolder.media_id == media_id,
    )
    stmt = _apply_scope_filters(
        stmt,
        FavoriteFolder,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )
    result = await db.execute(stmt.order_by(FavoriteFolder.id.asc()).limit(1))
    folder = result.scalar_one_or_none()

    if folder is None:
        folder = FavoriteFolder(
            session_id=session_id,
            media_id=media_id,
            title=title or "",
            media_count=media_count or 0,
            is_selected=True,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
        )
        db.add(folder)
        await db.flush()
    else:
        if title:
            folder.title = title
        if media_count is not None:
            folder.media_count = media_count

    return folder


async def get_existing_folder_for_scope(
    db: AsyncSession,
    session_id: str,
    media_id: int,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> Optional[FavoriteFolder]:
    stmt = select(FavoriteFolder).where(
        FavoriteFolder.session_id == session_id,
        FavoriteFolder.media_id == media_id,
    )
    stmt = _apply_scope_filters(
        stmt,
        FavoriteFolder,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )
    result = await db.execute(stmt.order_by(FavoriteFolder.id.asc()).limit(1))
    return result.scalar_one_or_none()


async def get_video_cache_for_scope(
    db: AsyncSession,
    bvid: str,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> Optional[VideoCache]:
    stmt = select(VideoCache).where(VideoCache.bvid == bvid)
    stmt = _apply_scope_filters(
        stmt,
        VideoCache,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )
    stmt = stmt.order_by(VideoCache.id.asc()).limit(1)
    result = await db.execute(stmt)
    return result.scalars().first()


def delete_video_vectors_for_scope(
    rag: RAGService,
    bvid: str,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
) -> None:
    if has_cache_scope(workspace_id, knowledge_base_id):
        rag.delete_video_in_knowledge_base(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
        return
    rag.delete_video(bvid)


async def upsert_video_cache(
    db: AsyncSession,
    bvid: str,
    meta: dict,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> None:
    """Write or update video cache metadata."""
    cache = await get_video_cache_for_scope(
        db,
        bvid,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )

    scoped_fields = {}
    if workspace_id is not None:
        scoped_fields["workspace_id"] = workspace_id
    if knowledge_base_id is not None:
        scoped_fields["knowledge_base_id"] = knowledge_base_id
    if source_binding_id is not None:
        scoped_fields["source_binding_id"] = source_binding_id

    if cache is None:
        cache = VideoCache(
            bvid=bvid,
            cid=meta.get("cid"),
            title=meta.get("title") or bvid,
            description=meta.get("intro"),
            owner_name=meta.get("owner_name"),
            owner_mid=meta.get("owner_mid"),
            duration=meta.get("duration"),
            pic_url=meta.get("cover"),
            is_processed=False,
            **scoped_fields,
        )
        db.add(cache)
        return

    cache.title = meta.get("title") or cache.title
    if meta.get("cid") is not None:
        cache.cid = meta.get("cid")
    if meta.get("intro") is not None:
        cache.description = meta.get("intro")
    if meta.get("owner_name") is not None:
        cache.owner_name = meta.get("owner_name")
    if meta.get("owner_mid") is not None:
        cache.owner_mid = meta.get("owner_mid")
    if meta.get("duration") is not None:
        cache.duration = meta.get("duration")
    if meta.get("cover") is not None:
        cache.pic_url = meta.get("cover")
    for key, val in scoped_fields.items():
        setattr(cache, key, val)
