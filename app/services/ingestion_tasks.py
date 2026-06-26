"""Helpers for persisted ingestion task lifecycle management."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import IngestionTask


DEFAULT_STALE_AFTER = timedelta(minutes=30)
INTERRUPTED_STEP = "任务已中断，请重新发起"
INTERRUPTED_MESSAGE = "服务重启或后台任务中断，任务未自动恢复，请重新发起。"


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def mark_stale_active_tasks_interrupted(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
    now: datetime | None = None,
) -> int:
    """Mark old pending/running ingestion tasks as interrupted after restart."""
    current_time = _as_aware_utc(now or datetime.now(timezone.utc))
    cutoff = current_time - stale_after
    interrupted_count = 0

    async with session_factory() as session:
        result = await session.execute(
            select(IngestionTask).where(
                IngestionTask.status.in_(("pending", "running"))
            )
        )
        for task in result.scalars():
            last_update = _as_aware_utc(task.updated_at or task.created_at)
            if last_update > cutoff:
                continue
            task.status = "interrupted"
            task.current_step = INTERRUPTED_STEP
            task.error_message = INTERRUPTED_MESSAGE
            interrupted_count += 1

        if interrupted_count:
            await session.commit()

    return interrupted_count
