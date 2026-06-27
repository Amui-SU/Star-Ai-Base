"""Helpers for persisted ingestion task lifecycle management."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import IngestionTask
from app.time_utils import as_aware_utc, utc_now


DEFAULT_STALE_AFTER = timedelta(minutes=30)
INTERRUPTED_STEP = "任务已中断，请重新发起"
INTERRUPTED_MESSAGE = "服务重启或后台任务中断，任务未自动恢复，请重新发起。"


async def create_ingestion_task(
    db: AsyncSession,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    user_id: int,
    current_step: str,
    source_binding_id: int | None = None,
    total_items: int = 0,
) -> str:
    task_id = str(uuid.uuid4())
    task = IngestionTask(
        task_id=task_id,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
        created_by=user_id,
        status="pending",
        progress=0,
        current_step=current_step,
        total_items=total_items,
        processed_items=0,
    )
    db.add(task)
    await db.commit()
    return task_id


def build_status_payload(task: IngestionTask) -> dict:
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "total_videos": task.total_items,
        "processed_videos": task.processed_items,
        "message": task.error_message or "",
        "workspace_id": task.workspace_id,
        "knowledge_base_id": task.knowledge_base_id,
    }


async def mark_stale_active_tasks_interrupted(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
    now: datetime | None = None,
) -> int:
    """Mark old pending/running ingestion tasks as interrupted after restart."""
    current_time = as_aware_utc(now or utc_now())
    cutoff = current_time - stale_after
    interrupted_count = 0

    async with session_factory() as session:
        result = await session.execute(
            select(IngestionTask).where(
                IngestionTask.status.in_(("pending", "running"))
            )
        )
        for task in result.scalars():
            last_update = as_aware_utc(task.updated_at or task.created_at)
            if last_update > cutoff:
                continue
            task.status = "interrupted"
            task.current_step = INTERRUPTED_STEP
            task.error_message = INTERRUPTED_MESSAGE
            interrupted_count += 1

        if interrupted_count:
            await session.commit()

    return interrupted_count
