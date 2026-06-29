from datetime import datetime

from app.models import FavoriteFolder
from app.models import FavoriteVideo
from app.models import VideoCache


async def add_folder(
    session,
    *,
    knowledge_base_id: int,
    media_id: int,
    title: str,
    synced: bool = True,
    updated_at: datetime | None = None,
    workspace_id: int | None = None,
    source_binding_id: int | None = None,
) -> FavoriteFolder:
    folder = FavoriteFolder(
        session_id=f"session-{knowledge_base_id}",
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
        media_id=media_id,
        title=title,
        last_sync_at=datetime(2026, 6, 13) if synced else None,
        updated_at=updated_at,
    )
    session.add(folder)
    await session.flush()
    return folder


async def add_video(
    session,
    *,
    folder: FavoriteFolder,
    bvid: str,
    title: str,
    processed: bool = True,
    favorite_knowledge_base_id: int | None = None,
    workspace_id: int | None = None,
    source_binding_id: int | None = None,
    cache_knowledge_base_id: int | None = None,
) -> None:
    session.add(
        FavoriteVideo(
            folder_id=folder.id,
            bvid=bvid,
            knowledge_base_id=(
                folder.knowledge_base_id
                if favorite_knowledge_base_id is None
                else favorite_knowledge_base_id
            ),
            workspace_id=workspace_id,
            source_binding_id=source_binding_id,
        )
    )
    session.add(
        VideoCache(
            bvid=bvid,
            title=title,
            workspace_id=workspace_id,
            knowledge_base_id=(
                folder.knowledge_base_id
                if cache_knowledge_base_id is None
                else cache_knowledge_base_id
            ),
            source_binding_id=source_binding_id,
            is_processed=processed,
        )
    )
