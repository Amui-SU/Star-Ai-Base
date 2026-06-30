from collections.abc import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    VideoCache,
    VideoTitleOverride,
)
from app.schemas.knowledge_base import (
    KnowledgeScopeFolder,
    KnowledgeScopeOptionsResponse,
    KnowledgeScopeVideo,
)


class InvalidKnowledgeScope(ValueError):
    """Raised when a requested chat scope is outside the knowledge base."""


def _nullable_equal(left, right):
    return or_(left == right, and_(left.is_(None), right.is_(None)))


def _video_cache_matches_favorite():
    return and_(
        VideoCache.bvid == FavoriteVideo.bvid,
        _nullable_equal(VideoCache.workspace_id, FavoriteVideo.workspace_id),
        _nullable_equal(VideoCache.knowledge_base_id, FavoriteVideo.knowledge_base_id),
        _nullable_equal(VideoCache.source_binding_id, FavoriteVideo.source_binding_id),
    )


async def _list_current_synced_folders(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
) -> list[FavoriteFolder]:
    folder_result = await db.execute(
        select(FavoriteFolder)
        .where(
            FavoriteFolder.knowledge_base_id == knowledge_base_id,
            FavoriteFolder.last_sync_at.is_not(None),
        )
        .order_by(
            FavoriteFolder.media_id,
            FavoriteFolder.updated_at.desc(),
            FavoriteFolder.id.desc(),
        )
    )

    current_folders: list[FavoriteFolder] = []
    seen_media_ids: set[int] = set()
    for folder in folder_result.scalars():
        if folder.media_id in seen_media_ids:
            continue
        seen_media_ids.add(folder.media_id)
        current_folders.append(folder)
    return current_folders


async def list_scope_options(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
) -> KnowledgeScopeOptionsResponse:
    folders = await _list_current_synced_folders(
        db,
        knowledge_base_id=knowledge_base_id,
    )
    if not folders:
        return KnowledgeScopeOptionsResponse(folders=[])

    folder_ids = [folder.id for folder in folders]
    video_result = await db.execute(
        select(
            FavoriteVideo.folder_id,
            VideoCache.bvid,
            VideoCache.title,
            VideoTitleOverride.custom_title,
        )
        .join(VideoCache, _video_cache_matches_favorite())
        .join(
            VideoTitleOverride,
            (VideoTitleOverride.workspace_id == FavoriteVideo.workspace_id)
            & (VideoTitleOverride.knowledge_base_id == FavoriteVideo.knowledge_base_id)
            & or_(
                VideoTitleOverride.source_binding_id == FavoriteVideo.source_binding_id,
                and_(
                    VideoTitleOverride.source_binding_id.is_(None),
                    FavoriteVideo.source_binding_id.is_(None),
                ),
            )
            & (VideoTitleOverride.bvid == FavoriteVideo.bvid),
            isouter=True,
        )
        .where(
            FavoriteVideo.folder_id.in_(folder_ids),
            FavoriteVideo.knowledge_base_id == knowledge_base_id,
            VideoCache.is_processed.is_(True),
        )
        .order_by(
            FavoriteVideo.folder_id,
            VideoCache.bvid,
            VideoTitleOverride.id.desc(),
        )
    )

    videos_by_folder: dict[int, list[KnowledgeScopeVideo]] = {
        folder_id: [] for folder_id in folder_ids
    }
    seen_by_folder: dict[int, set[str]] = {folder_id: set() for folder_id in folder_ids}
    for folder_id, bvid, title, custom_title in video_result:
        if bvid in seen_by_folder[folder_id]:
            continue
        seen_by_folder[folder_id].add(bvid)
        if custom_title:
            videos_by_folder[folder_id].append(
                KnowledgeScopeVideo(
                    bvid=bvid,
                    title=custom_title,
                    original_title=title,
                    custom_title=custom_title,
                    display_title=custom_title,
                )
            )
        else:
            videos_by_folder[folder_id].append(
                KnowledgeScopeVideo(bvid=bvid, title=title)
            )

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
    current_folders = await _list_current_synced_folders(
        db,
        knowledge_base_id=knowledge_base_id,
    )
    current_folders_by_media_id = {
        folder.media_id: folder for folder in current_folders
    }
    current_folder_row_ids = [folder.id for folder in current_folders]

    if requested_folder_ids:
        valid_folder_ids = set(current_folders_by_media_id).intersection(
            requested_folder_ids
        )
        invalid_folder_ids = sorted(set(requested_folder_ids) - valid_folder_ids)
        if invalid_folder_ids:
            invalid = ", ".join(str(media_id) for media_id in invalid_folder_ids)
            raise InvalidKnowledgeScope(f"Invalid folder_ids: {invalid}")

        selected_folder_row_ids = [
            current_folders_by_media_id[media_id].id
            for media_id in requested_folder_ids
        ]
        folder_video_result = await db.execute(
            select(VideoCache.bvid)
            .select_from(FavoriteVideo)
            .join(VideoCache, _video_cache_matches_favorite())
            .where(
                FavoriteVideo.folder_id.in_(selected_folder_row_ids),
                FavoriteVideo.knowledge_base_id == knowledge_base_id,
                VideoCache.is_processed.is_(True),
            )
        )
        resolved_bvids.update(folder_video_result.scalars())

    if requested_video_ids:
        valid_bvids: set[str] = set()
        if current_folder_row_ids:
            video_result = await db.execute(
                select(VideoCache.bvid)
                .select_from(FavoriteVideo)
                .join(VideoCache, _video_cache_matches_favorite())
                .where(
                    FavoriteVideo.folder_id.in_(current_folder_row_ids),
                    FavoriteVideo.knowledge_base_id == knowledge_base_id,
                    VideoCache.bvid.in_(requested_video_ids),
                    VideoCache.is_processed.is_(True),
                )
                .distinct()
            )
            valid_bvids.update(video_result.scalars())
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
