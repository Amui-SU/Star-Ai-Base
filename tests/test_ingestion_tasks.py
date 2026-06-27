from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import IngestionTask


@pytest.mark.asyncio
async def test_create_ingestion_task_persists_standard_defaults(db_session_factory):
    from app.services.ingestion_tasks import create_ingestion_task

    async with db_session_factory() as session:
        task_id = await create_ingestion_task(
            session,
            workspace_id=3,
            knowledge_base_id=9,
            user_id=5,
            source_binding_id=7,
            current_step="Preparing import",
            total_items=2,
        )

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(IngestionTask.task_id == task_id)
                )
            )
            .scalars()
            .one()
        )

    assert task.workspace_id == 3
    assert task.knowledge_base_id == 9
    assert task.source_binding_id == 7
    assert task.created_by == 5
    assert task.status == "pending"
    assert task.progress == 0
    assert task.current_step == "Preparing import"
    assert task.total_items == 2
    assert task.processed_items == 0


def test_build_status_payload_preserves_existing_response_keys():
    from app.services.ingestion_tasks import build_status_payload

    task = IngestionTask(
        task_id="status-task",
        workspace_id=3,
        knowledge_base_id=9,
        source_binding_id=None,
        created_by=5,
        status="running",
        progress=42,
        current_step="Indexing",
        total_items=8,
        processed_items=4,
        error_message=None,
    )

    assert build_status_payload(task) == {
        "task_id": "status-task",
        "status": "running",
        "progress": 42,
        "current_step": "Indexing",
        "total_videos": 8,
        "processed_videos": 4,
        "message": "",
        "workspace_id": 3,
        "knowledge_base_id": 9,
    }


@pytest.mark.asyncio
async def test_update_ingestion_task_mutates_existing_task(
    db_session_factory, monkeypatch
):
    import app.database as database
    from app.services.ingestion_tasks import update_ingestion_task

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="update-task",
                workspace_id=3,
                knowledge_base_id=9,
                created_by=5,
                status="pending",
                progress=0,
                current_step="Waiting",
                total_items=2,
                processed_items=0,
            )
        )
        await session.commit()

    updated = await update_ingestion_task(
        "update-task",
        status="running",
        progress=45,
        current_step="Indexing",
        processed_items=1,
        error_message=None,
    )

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(IngestionTask.task_id == "update-task")
                )
            )
            .scalars()
            .one()
        )

    assert updated is True
    assert task.status == "running"
    assert task.progress == 45
    assert task.current_step == "Indexing"
    assert task.processed_items == 1
    assert task.error_message is None


@pytest.mark.asyncio
async def test_update_ingestion_task_returns_false_for_missing_task(
    db_session_factory, monkeypatch
):
    import app.database as database
    from app.services.ingestion_tasks import update_ingestion_task

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    updated = await update_ingestion_task("missing-task", status="running")

    assert updated is False


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
