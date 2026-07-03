"""Favorite-video association helpers for folder ingestion."""

from collections.abc import Callable
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteVideo
from app.services.folder_ingestion_records import (
    delete_video_vectors_for_scope,
    has_cache_scope,
)
from app.services.rag import RAGService


def _noop_log(_message: str) -> None:
    return None


async def count_folder_video_rows(db: AsyncSession, folder_id: int) -> int:
    count = await db.scalar(
        select(func.count(FavoriteVideo.bvid)).where(
            FavoriteVideo.folder_id == folder_id
        )
    )
    return count or 0


async def count_distinct_folder_videos(db: AsyncSession, folder_id: int) -> int:
    count = await db.scalar(
        select(func.count(func.distinct(FavoriteVideo.bvid)))
        .select_from(FavoriteVideo)
        .where(FavoriteVideo.folder_id == folder_id)
    )
    return count or 0


async def get_existing_folder_bvids(db: AsyncSession, folder_id: int) -> set[str]:
    existing_rows = await db.execute(
        select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder_id)
    )
    return {row[0] for row in existing_rows.fetchall()}


async def ensure_favorite_video(
    db: AsyncSession,
    *,
    folder_id: int,
    bvid: str,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> None:
    exists_row = await db.execute(
        select(FavoriteVideo.id).where(
            FavoriteVideo.folder_id == folder_id,
            FavoriteVideo.bvid == bvid,
        )
    )
    if exists_row.scalar_one_or_none() is not None:
        return

    fav_kwargs: dict = {
        "folder_id": folder_id,
        "bvid": bvid,
        "is_selected": True,
    }
    if workspace_id is not None:
        fav_kwargs["workspace_id"] = workspace_id
    if knowledge_base_id is not None:
        fav_kwargs["knowledge_base_id"] = knowledge_base_id
    if source_binding_id is not None:
        fav_kwargs["source_binding_id"] = source_binding_id
    db.add(FavoriteVideo(**fav_kwargs))


async def _count_other_references_in_scope(
    db: AsyncSession,
    *,
    folder_id: int,
    bvid: str,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(FavoriteVideo)
        .where(
            FavoriteVideo.bvid == bvid,
            FavoriteVideo.folder_id != folder_id,
        )
    )
    if has_cache_scope(workspace_id, knowledge_base_id):
        stmt = (
            stmt.where(FavoriteVideo.workspace_id == workspace_id)
            .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
            .where(
                FavoriteVideo.source_binding_id.is_(None)
                if source_binding_id is None
                else FavoriteVideo.source_binding_id == source_binding_id
            )
        )
    else:
        stmt = stmt.where(FavoriteVideo.workspace_id.is_(None)).where(
            FavoriteVideo.knowledge_base_id.is_(None)
        )
    count = await db.scalar(stmt)
    return count or 0


async def remove_stale_favorite_videos(
    db: AsyncSession,
    *,
    rag: RAGService,
    folder_id: int,
    removed: set[str],
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
    warn: Callable[[str], None] = _noop_log,
) -> None:
    if not removed:
        return

    for bvid in removed:
        other_count = await _count_other_references_in_scope(
            db,
            folder_id=folder_id,
            bvid=bvid,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
        )
        if other_count == 0:
            try:
                delete_video_vectors_for_scope(
                    rag,
                    bvid,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                )
            except Exception as e:
                warn(f"删除向量失败 [{bvid}]: {e}")

    await db.execute(
        delete(FavoriteVideo).where(
            FavoriteVideo.folder_id == folder_id,
            FavoriteVideo.bvid.in_(removed),
        )
    )
