"""Persistence helpers for imported video content."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from app.database import get_db_context
from app.models import FavoriteFolder, FavoriteVideo, VideoCache
from app.schemas.content import VideoContent
from app.time_utils import utc_now


async def store_imported_video_content(
    *,
    content: VideoContent,
    workspace_id: int,
    knowledge_base_id: int,
    cid: int | None = None,
    description: str | None = None,
    owner_name: str | None = None,
    owner_mid: int | None = None,
    duration: int | None = None,
    pic_url: str | None = None,
    # 分P元信息（用于AI时间戳功能）
    page_number: int | None = None,
    part_title: str | None = None,
    total_parts: int | None = None,
    folder_title: str = "单条视频导入",
    db_context_factory: Callable[[], Any] = get_db_context,
) -> None:
    async with db_context_factory() as db:
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.bvid == content.bvid)
            .where(VideoCache.workspace_id == workspace_id)
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(VideoCache.source_binding_id.is_(None))
        )
        cache = result.scalar_one_or_none()
        if cache is None:
            cache = VideoCache(
                bvid=content.bvid,
                title=content.title,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=None,
                is_processed=True,
            )
            db.add(cache)
        if cid is not None:
            cache.cid = cid
        cache.title = content.title
        cache.description = description
        cache.owner_name = owner_name
        cache.owner_mid = owner_mid
        cache.duration = duration
        cache.pic_url = pic_url
        cache.content = content.content
        cache.content_source = content.source.value
        cache.outline_json = content.outline
        # 保存分P元信息和时间轴数据
        cache.page_number = page_number
        cache.part_title = part_title
        cache.total_parts = total_parts
        cache.subtitle_timeline_json = content.subtitle_timeline
        cache.is_processed = True
        cache.workspace_id = workspace_id
        cache.knowledge_base_id = knowledge_base_id
        cache.source_binding_id = None

        folder_result = await db.execute(
            select(FavoriteFolder)
            .where(FavoriteFolder.workspace_id == workspace_id)
            .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
            .where(FavoriteFolder.media_id == 0)
            .where(FavoriteFolder.title == folder_title)
        )
        folder = folder_result.scalar_one_or_none()
        if folder is None:
            folder = FavoriteFolder(
                session_id="",
                media_id=0,
                title=folder_title,
                media_count=0,
                is_selected=True,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=None,
            )
            db.add(folder)
            await db.flush()

        exists = await db.execute(
            select(FavoriteVideo.id)
            .where(FavoriteVideo.folder_id == folder.id)
            .where(FavoriteVideo.bvid == content.bvid)
        )
        if exists.scalar_one_or_none() is None:
            db.add(
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid=content.bvid,
                    is_selected=True,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=None,
                )
            )
            folder.media_count = (folder.media_count or 0) + 1
        folder.last_sync_at = utc_now()
        await db.commit()
