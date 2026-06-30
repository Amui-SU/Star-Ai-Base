"""Knowledge-base build task execution and status helpers."""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.models import IngestionTask, KnowledgeBase
from app.services.folder_ingestion import sync_folder
from app.services.ingestion_tasks import build_status_payload, update_ingestion_task
from app.services.knowledge_base_presenters import dedupe_ints

TaskUpdater = Callable[..., Awaitable[bool]]
FolderSyncer = Callable[..., Awaitable[object]]


async def run_scoped_build(
    task_id: str,
    bili,
    rag,
    content_fetcher,
    folder_ids: list[int],
    video_folder_ids: list[int] | None,
    include_bvids: set[str] | None,
    exclude_bvids: set[str],
    workspace_id: int,
    knowledge_base_id: int,
    source_binding_id: int,
    *,
    update_task: TaskUpdater = update_ingestion_task,
    sync_folder_func: FolderSyncer = sync_folder,
    db_context_factory=get_db_context,
    log_error: Callable[[str], None] = logger.error,
) -> None:
    """后台执行知识库构建任务，通过 IngestionTask 持久化状态。"""
    try:
        await update_task(task_id, status="running", current_step="同步收藏夹...")

        async with db_context_factory() as db:
            full_folder_ids = dedupe_ints(folder_ids)
            full_folder_set = set(full_folder_ids)
            partial_folder_ids = [
                folder_id
                for folder_id in dedupe_ints(video_folder_ids)
                if folder_id not in full_folder_set
            ]
            steps = [(folder_id, None) for folder_id in full_folder_ids]
            if include_bvids:
                steps.extend(
                    (folder_id, include_bvids) for folder_id in partial_folder_ids
                )

            total_folders = len(steps) or 1
            for idx, (folder_id, folder_include_bvids) in enumerate(steps, start=1):
                await update_task(
                    task_id,
                    current_step=f"同步收藏夹 {folder_id} ({idx}/{total_folders})",
                    progress=int((idx - 1) / total_folders * 100),
                )

                await sync_folder_func(
                    db=db,
                    bili=bili,
                    rag=rag,
                    content_fetcher=content_fetcher,
                    session_id="",
                    folder_id=folder_id,
                    exclude_bvids=exclude_bvids,
                    include_bvids=folder_include_bvids,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=source_binding_id,
                )

        await update_task(
            task_id,
            status="completed",
            progress=100,
            current_step="完成",
        )
    except Exception as exc:
        log_error(f"构建任务失败 [{task_id}]: {exc}")
        await update_task(
            task_id, status="failed", error_message=str(exc), current_step="失败"
        )
    finally:
        await bili.close()


async def get_build_status_payload(
    db: AsyncSession,
    *,
    task_id: str,
    knowledge_base: KnowledgeBase,
) -> dict:
    result = await db.execute(
        select(IngestionTask).where(IngestionTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.knowledge_base_id != knowledge_base.id:
        raise HTTPException(status_code=404, detail="任务不属于当前知识库")
    return build_status_payload(task)
