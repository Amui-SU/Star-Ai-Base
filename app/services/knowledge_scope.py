from collections.abc import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    KnowledgeScopeFolder,
    KnowledgeScopeOptionsResponse,
    KnowledgeScopeVideo,
    VideoCache,
)


class InvalidKnowledgeScope(ValueError):
    """Raised when a requested chat scope is outside the knowledge base."""


async def list_scope_options(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
) -> KnowledgeScopeOptionsResponse:
    folder_result = await db.execute(
        select(FavoriteFolder)
        .where(
            FavoriteFolder.knowledge_base_id == knowledge_base_id,
            FavoriteFolder.last_sync_at.is_not(None),
        )
        .order_by(FavoriteFolder.media_id, FavoriteFolder.id)
    )
    folders = list(folder_result.scalars())
    if not folders:
        return KnowledgeScopeOptionsResponse(folders=[])

    folder_ids = [folder.id for folder in folders]
    video_result = await db.execute(
        select(FavoriteVideo.folder_id, VideoCache.bvid, VideoCache.title)
        .join(
            VideoCache,
            and_(
                VideoCache.bvid == FavoriteVideo.bvid,
                VideoCache.knowledge_base_id == knowledge_base_id,
            ),
        )
        .where(
            FavoriteVideo.folder_id.in_(folder_ids),
            FavoriteVideo.knowledge_base_id == knowledge_base_id,
            VideoCache.knowledge_base_id == knowledge_base_id,
            VideoCache.is_processed.is_(True),
        )
        .order_by(FavoriteVideo.folder_id, VideoCache.bvid)
    )

    videos_by_folder: dict[int, list[KnowledgeScopeVideo]] = {
        folder_id: [] for folder_id in folder_ids
    }
    seen_by_folder: dict[int, set[str]] = {folder_id: set() for folder_id in folder_ids}
    for folder_id, bvid, title in video_result:
        if bvid in seen_by_folder[folder_id]:
            continue
        seen_by_folder[folder_id].add(bvid)
        videos_by_folder[folder_id].append(KnowledgeScopeVideo(bvid=bvid, title=title))

    return KnowledgeScopeOptionsResponse(
        folders=[
            KnowledgeScopeFolder(
                media_id=folder.media_id,
                title=folder.title,
                video_count=len(videos_by_folder[folder.id]),
                videos=videos_by_folder[folder.id],
            )
            for folder in folders
        ]
    )


async def resolve_scope_bvids(
    db: AsyncSession,
    knowledge_base_id: int,
    folder_media_ids: Sequence[int] | None,
    requested_bvids: Sequence[str] | None,
) -> list[str] | None:
    requested_folder_ids = sorted(set(folder_media_ids or []))
    requested_video_ids = sorted(set(requested_bvids or []))
    if not requested_folder_ids and not requested_video_ids:
        return None

    resolved_bvids: set[str] = set()
    selected_folder_row_ids: list[int] = []

    if requested_folder_ids:
        folder_result = await db.execute(
            select(FavoriteFolder.id, FavoriteFolder.media_id).where(
                FavoriteFolder.knowledge_base_id == knowledge_base_id,
                FavoriteFolder.last_sync_at.is_not(None),
                FavoriteFolder.media_id.in_(requested_folder_ids),
            )
        )
        selected_folders = list(folder_result)
        valid_folder_ids = {media_id for _, media_id in selected_folders}
        invalid_folder_ids = sorted(set(requested_folder_ids) - valid_folder_ids)
        if invalid_folder_ids:
            invalid = ", ".join(str(media_id) for media_id in invalid_folder_ids)
            raise InvalidKnowledgeScope(f"Invalid folder_ids: {invalid}")

        selected_folder_row_ids = [folder_id for folder_id, _ in selected_folders]
        folder_video_result = await db.execute(
            select(VideoCache.bvid)
            .select_from(FavoriteVideo)
            .join(
                VideoCache,
                and_(
                    VideoCache.bvid == FavoriteVideo.bvid,
                    VideoCache.knowledge_base_id == knowledge_base_id,
                ),
            )
            .where(
                FavoriteVideo.folder_id.in_(selected_folder_row_ids),
                FavoriteVideo.knowledge_base_id == knowledge_base_id,
                VideoCache.knowledge_base_id == knowledge_base_id,
                VideoCache.is_processed.is_(True),
            )
        )
        resolved_bvids.update(folder_video_result.scalars())

    if requested_video_ids:
        video_result = await db.execute(
            select(VideoCache.bvid)
            .select_from(FavoriteVideo)
            .join(
                VideoCache,
                and_(
                    VideoCache.bvid == FavoriteVideo.bvid,
                    VideoCache.knowledge_base_id == knowledge_base_id,
                ),
            )
            .where(
                FavoriteVideo.knowledge_base_id == knowledge_base_id,
                VideoCache.knowledge_base_id == knowledge_base_id,
                VideoCache.bvid.in_(requested_video_ids),
                VideoCache.is_processed.is_(True),
            )
            .distinct()
        )
        valid_bvids = set(video_result.scalars())
        invalid_bvids = sorted(set(requested_video_ids) - valid_bvids)
        if invalid_bvids:
            raise InvalidKnowledgeScope(f"Invalid bvids: {', '.join(invalid_bvids)}")
        resolved_bvids.update(valid_bvids)

    if not resolved_bvids:
        identifiers = []
        if requested_folder_ids:
            identifiers.append(
                "folder_ids=" + ",".join(str(item) for item in requested_folder_ids)
            )
        if requested_video_ids:
            identifiers.append("bvids=" + ",".join(requested_video_ids))
        raise InvalidKnowledgeScope(
            "Scope selection has no retrievable videos: " + "; ".join(identifiers)
        )

    return sorted(resolved_bvids)
