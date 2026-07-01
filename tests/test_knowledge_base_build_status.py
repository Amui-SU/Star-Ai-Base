import pytest
from sqlalchemy import select

from app.models import IngestionTask, SystemSession
from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_build_status_polling_does_not_touch_session_last_seen(
    client,
    db_session_factory,
):
    auth = await register_user(client, "poll-status@example.com", "Poll Status")
    knowledge_base = await create_knowledge_base(client, "Poll Status KB")
    task_id = "poll-status-task"

    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        before = auth_session.last_seen_at
        session.add(
            IngestionTask(
                task_id=task_id,
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
                source_binding_id=None,
                created_by=auth["user"]["id"],
                status="running",
                progress=42,
                current_step="polling",
            )
        )
        await session.commit()

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/build/status/{task_id}"
    )

    assert response.status_code == 200
    assert response.json()["progress"] == 42
    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        assert auth_session.last_seen_at == before
