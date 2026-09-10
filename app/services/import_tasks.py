"""Background import task runtime helpers."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.schemas.content import ContentSource, VideoContent
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.folder_ingestion_content import (
    should_refresh_cache,
    video_content_from_cache,
)
from app.services.ingestion_tasks import update_ingestion_task
from app.services.import_persistence import store_imported_video_content
from app.services.rag_runtime import get_rag_service

# 分P批量导入的并发上限（过高有 B 站风控风险）
MULTI_PART_IMPORT_CONCURRENCY = 2


async def load_reusable_import_content(
    storage_bvid: str,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    title: str | None = None,
) -> VideoContent | None:
    """重复导入时复用已有的高质量缓存内容（字幕/ASR），避免重新转写"""
    from app.database import get_db_context
    from app.models import VideoCache

    async with get_db_context() as db:
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.bvid == storage_bvid)
            .where(VideoCache.workspace_id == workspace_id)
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(VideoCache.source_binding_id.is_(None))
        )
        cache = result.scalar_one_or_none()
    if should_refresh_cache(cache):
        return None
    return video_content_from_cache(
        cache,
        storage_bvid,
        title or cache.title or storage_bvid,
    )


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


async def run_bilibili_video_import(
    task_id: str,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
    cid: int | None = None,
    # 分P元信息
    page_number: int | None = None,
    part_title: str | None = None,
    total_parts: int | None = None,
    part_duration: int | None = None,
    storage_bvid: str | None = None,
    title_override: str | None = None,
    video_info: dict | None = None,
    *,
    bilibili_service_class: type[BilibiliService] = BilibiliService,
    asr_service_class: type[ASRService] = ASRService,
    content_fetcher_class: type[ContentFetcher] = ContentFetcher,
    rag_factory: Callable[[], Any] = get_rag_service,
    update_task: Callable[..., Any] = update_ingestion_task,
    store_content: Callable[..., Any] = store_imported_video_content,
    delete_vectors: Callable[..., None] = delete_existing_import_vectors,
    load_cached_content: Callable[..., Any] = load_reusable_import_content,
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

        # 重复导入时复用缓存内容，跳过抓取/转写，只重建向量
        cached_content = await load_cached_content(
            storage_bvid or bvid,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            title=title_override,
        )
        if cached_content is not None:
            content = cached_content
            await update_task(
                task_id,
                current_step="复用已有转写内容...",
                progress=60,
            )
        else:
            info = video_info
            if info is None:
                info = await bili.get_video_info(bvid)
            title = title_override or info.get("title") or bvid

            # 如果没有指定cid，使用视频默认的cid
            if cid is None:
                cid = info.get("cid")

            await update_task(task_id, current_step="提取视频内容...", progress=36)
            content = await fetcher.fetch_content(
                bvid,
                cid=cid,
                title=info.get("title") or bvid,
                video_info=info,
            )

            # 分P导入：以存储ID（bvid_p{page}）落库，让每个分P独立缓存/向量化
            if title_override:
                content.title = title_override
            if storage_bvid and storage_bvid != bvid:
                content.bvid = storage_bvid

            await store_content(
                content=content,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                cid=cid,
                description=info.get("desc"),
                owner_name=(info.get("owner") or {}).get("name"),
                owner_mid=(info.get("owner") or {}).get("mid"),
                duration=(
                    part_duration if part_duration is not None else info.get("duration")
                ),
                pic_url=info.get("pic"),
                # 传递分P元信息
                page_number=page_number,
                part_title=part_title,
                total_parts=total_parts,
            )

        await update_task(task_id, current_step="写入向量索引...", progress=76)
        delete_vectors(
            rag,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=content.bvid,
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


async def run_multi_part_video_imports(
    jobs: list[dict],
    *,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
    video_info: dict | None = None,
    concurrency: int = MULTI_PART_IMPORT_CONCURRENCY,
    run_import: Callable[..., Any] = run_bilibili_video_import,
) -> None:
    """受控并发执行一批分P导入；单P失败已在 run_import 内落任务状态，不影响其余分P"""
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(job: dict) -> None:
        async with semaphore:
            await run_import(
                task_id=job["task_id"],
                bvid=bvid,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                cid=job.get("cid"),
                page_number=job.get("page"),
                part_title=job.get("part"),
                total_parts=job.get("total_parts"),
                part_duration=job.get("duration"),
                storage_bvid=job.get("storage_bvid"),
                title_override=job.get("title"),
                video_info=video_info,
            )

    await asyncio.gather(*(run_one(job) for job in jobs))


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
