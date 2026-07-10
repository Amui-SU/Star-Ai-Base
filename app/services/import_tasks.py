"""Background import task runtime helpers."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from app.schemas.content import ContentSource, VideoContent
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.ingestion_tasks import update_ingestion_task
from app.services.import_persistence import store_imported_video_content
from app.services.rag_runtime import get_rag_service


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

        # 如果没有指定cid，使用视频默认的cid
        if cid is None:
            cid = info.get("cid")

        await update_task(task_id, current_step="提取视频内容...", progress=36)
        content = await fetcher.fetch_content(bvid, cid=cid, title=title)

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
