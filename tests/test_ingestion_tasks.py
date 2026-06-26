from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import IngestionTask


@pytest.mark.asyncio
async def test_mark_stale_active_tasks_as_interrupted(db_session_factory):
    from app.services.ingestion_tasks import mark_stale_active_tasks_interrupted

    now = datetime.now(timezone.utc)
    stale_running = now - timedelta(hours=2)
    stale_pending = now - timedelta(hours=3)
    fresh_running = now - timedelta(minutes=5)

    async with db_session_factory() as session:
        session.add_all(
            [
                IngestionTask(
                    task_id="stale-running",
                    workspace_id=1,
                    knowledge_base_id=10,
                    created_by=100,
                    status="running",
                    progress=48,
                    current_step="同步收藏夹...",
                    updated_at=stale_running,
                ),
                IngestionTask(
                    task_id="stale-pending",
                    workspace_id=1,
                    knowledge_base_id=10,
                    created_by=100,
                    status="pending",
                    progress=0,
                    current_step="等待执行...",
                    updated_at=stale_pending,
                ),
                IngestionTask(
                    task_id="fresh-running",
                    workspace_id=1,
                    knowledge_base_id=10,
                    created_by=100,
                    status="running",
                    progress=12,
                    current_step="刚刚开始...",
                    updated_at=fresh_running,
                ),
                IngestionTask(
                    task_id="already-failed",
                    workspace_id=1,
                    knowledge_base_id=10,
                    created_by=100,
                    status="failed",
                    progress=12,
                    current_step="失败",
                    updated_at=stale_running,
                ),
            ]
        )
        await session.commit()

    interrupted_count = await mark_stale_active_tasks_interrupted(
        db_session_factory,
        stale_after=timedelta(hours=1),
        now=now,
    )

    async with db_session_factory() as session:
        tasks = {
            task.task_id: task
            for task in (await session.execute(select(IngestionTask))).scalars()
        }

    assert interrupted_count == 2
    assert tasks["stale-running"].status == "interrupted"
    assert tasks["stale-running"].progress == 48
    assert tasks["stale-running"].current_step == "任务已中断，请重新发起"
    assert "服务重启或后台任务中断" in tasks["stale-running"].error_message
    assert tasks["stale-pending"].status == "interrupted"
    assert tasks["fresh-running"].status == "running"
    assert tasks["fresh-running"].current_step == "刚刚开始..."
    assert tasks["already-failed"].status == "failed"


@pytest.mark.asyncio
async def test_lifespan_marks_stale_ingestion_tasks_interrupted(monkeypatch):
    import app.main as main

    calls = []
    session_factory = object()

    async def fake_init_db():
        calls.append(("init_db", None))

    async def fake_mark_stale_tasks(factory):
        calls.append(("recover", factory))
        return 2

    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main, "async_session_factory", session_factory, raising=False)
    monkeypatch.setattr(
        main,
        "mark_stale_active_tasks_interrupted",
        fake_mark_stale_tasks,
        raising=False,
    )

    async with main.lifespan(main.app):
        pass

    assert calls == [("init_db", None), ("recover", session_factory)]
