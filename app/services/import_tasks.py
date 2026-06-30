"""Background import task runtime helpers."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.database import get_db_context
from app.models import (
    ContentSource,
    FavoriteFolder,
    FavoriteVideo,
    VideoCache,
    VideoContent,
)
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.ingestion_tasks import update_ingestion_task
from app.services.rag_runtime import get_rag_service
from app.time_utils import utc_now


def delete_existing_import_vectors(
    rag,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
    warning_logger: Callable[[str], None] = logger.warning,
) -> None:
    try:
        rag.delete_video_in_knowledge_base(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
    except Exception as exc:
        warning_logger(
            "Import vector cleanup failed "
            f"[workspace={workspace_id}, knowledge_base={knowledge_base_id}, "
            f"bvid={bvid}]: {exc}"
        )


def cleanup_local_upload(
    file_path: str,
    *,
    path_factory: Callable[[str], Path] = Path,
    warning_logger: Callable[[str], None] = logger.warning,
) -> None:
    try:
        upload_path = path_factory(file_path)
        if upload_path.exists():
            upload_path.unlink()
    except Exception as exc:
        warning_logger(f"Local upload cleanup failed [{file_path}]: {exc}")


async def store_imported_video_content(
    *,
    content: VideoContent,
    workspace_id: int,
    knowledge_base_id: int,
    description: str | None = None,
    owner_name: str | None = None,
    owner_mid: int | None = None,
    duration: int | None = None,
    pic_url: str | None = None,
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
        cache.title = content.title
        cache.description = description
        cache.owner_name = owner_name
        cache.owner_mid = owner_mid
        cache.duration = duration
        cache.pic_url = pic_url
        cache.content = content.content
        cache.content_source = content.source.value
        cache.outline_json = content.outline
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


async def run_bilibili_video_import(
    task_id: str,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
    *,
    bilibili_service_class: type[BilibiliService] = BilibiliService,
    asr_service_class: type[ASRService] = ASRService,
    content_fetcher_class: type[ContentFetcher] = ContentFetcher,
    rag_factory: Callable[[], Any] = get_rag_service,
    update_task: Callable[..., Any] = update_ingestion_task,
    store_content: Callable[..., Any] = store_imported_video_content,
    delete_vectors: Callable[..., None] = delete_existing_import_vectors,
) -> None:
    bili = bilibili_service_class()
    asr = asr_service_class()
    fetcher = content_fetcher_class(bili, asr)
    try:
        rag = rag_factory()
        await update_task(
            task_id,
            status="running",
            current_step="获取视频信息...",
            progress=12,
        )
        info = await bili.get_video_info(bvid)
        title = info.get("title") or bvid
        cid = info.get("cid")

        await update_task(task_id, current_step="提取视频内容...", progress=36)
        content = await fetcher.fetch_content(bvid, cid=cid, title=title)

        await store_content(
            content=content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            description=info.get("desc"),
            owner_name=(info.get("owner") or {}).get("name"),
            owner_mid=(info.get("owner") or {}).get("mid"),
            duration=info.get("duration"),
            pic_url=info.get("pic"),
        )

        await update_task(task_id, current_step="写入向量索引...", progress=76)
        delete_vectors(
            rag,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
        rag.add_video_content(
            content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        await update_task(
            task_id,
            status="completed",
            progress=100,
            processed_items=1,
            current_step="导入完成",
            error_message=None,
        )
    except Exception as exc:
        await update_task(
            task_id,
            status="failed",
            current_step="导入失败",
            error_message=str(exc),
        )
    finally:
        await bili.close()


async def run_local_video_import(
    task_id: str,
    local_id: str,
    title: str,
    file_path: str,
    workspace_id: int,
    knowledge_base_id: int,
    *,
    asr_service_class: type[ASRService] = ASRService,
    rag_factory: Callable[[], Any] = get_rag_service,
    update_task: Callable[..., Any] = update_ingestion_task,
    store_content: Callable[..., Any] = store_imported_video_content,
    delete_vectors: Callable[..., None] = delete_existing_import_vectors,
    cleanup_upload: Callable[[str], None] = cleanup_local_upload,
) -> None:
    asr = asr_service_class()
    try:
        rag = rag_factory()
        await update_task(
            task_id,
            status="running",
            current_step="转写本地视频...",
            progress=28,
        )
        transcript = await asr.transcribe_local_file(file_path)
        if not transcript or len(transcript.strip()) < 10:
            raise ValueError("未能从本地视频中识别到有效文本")

        content = VideoContent(
            bvid=local_id,
            title=title,
            content=transcript.strip(),
            source=ContentSource.ASR,
        )

        await store_content(
            content=content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            description=f"本地视频文件：{Path(file_path).name}",
        )

        await update_task(task_id, current_step="写入向量索引...", progress=76)
        delete_vectors(
            rag,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=local_id,
        )
        rag.add_video_content(
            content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        await update_task(
            task_id,
            status="completed",
            progress=100,
            processed_items=1,
            current_step="导入完成",
            error_message=None,
        )
    except Exception as exc:
        await update_task(
            task_id,
            status="failed",
            current_step="导入失败",
            error_message=str(exc),
        )
    finally:
        cleanup_upload(file_path)
