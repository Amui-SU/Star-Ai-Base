import pytest
from sqlalchemy import select

from app.models import IngestionTask, SystemSession
from tests.test_knowledge_base_scoping import (
    create_knowledge_base,
    create_source_binding,
    register_user,
    seed_scope_folder,
)


@pytest.mark.asyncio
async def test_scoped_chat_unions_folder_and_explicit_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Chat KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1FOLDER", "Folder video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=20,
        title="Explicit video folder",
        videos=[("BV1EXPLICIT", "Explicit video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={
            "question": "scope this",
            "folder_ids": [10],
            "bvids": ["BV1EXPLICIT"],
        },
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1EXPLICIT", "BV1FOLDER"]


@pytest.mark.asyncio
async def test_scoped_search_passes_resolved_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Search KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1SEARCH", "Search video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1SEARCH"]


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_same_resolved_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Stream KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1STREAM", "Stream video")],
    )
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1STREAM"]


@pytest.mark.asyncio
async def test_scoped_chat_rejects_external_bvid(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "scope this", "bvids": ["BV2EXTERNAL"]},
    )

    assert response.status_code == 400
    assert "BV2EXTERNAL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scope_options_only_returns_current_knowledge_base(
    client,
    db_session_factory,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Current folder",
        videos=[("BV1CURRENT", "Current video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/scope-options"
    )

    assert response.status_code == 200
    assert response.json() == {
        "folders": [
            {
                "media_id": 10,
                "title": "Current folder",
                "video_count": 1,
                "videos": [
                    {"bvid": "BV1CURRENT", "title": "Current video"},
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_scope_options_requires_login(client):
    response = await client.get("/knowledge-bases/1/scope-options")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scope_options_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/scope-options")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_rejects_unknown_source_binding(client):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build KB")

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": 999, "folder_ids": [1]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_records_scope_metadata(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    async def fake_run_scoped_build(**_kwargs):
        pass

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build Metadata KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [1, 2]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["workspace_id"] == knowledge_base["workspace_id"]
    assert body["knowledge_base_id"] == knowledge_base["id"]
    assert body["source_binding_id"] == binding.id
    assert body["task_id"]


@pytest.mark.asyncio
async def test_scoped_build_accepts_single_video_selection(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "video-build@example.com", "Video Build")
    knowledge_base = await create_knowledge_base(client, "Video Build KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={
            "source_binding_id": binding.id,
            "folder_ids": [],
            "video_folder_ids": [10],
            "bvids": ["BV1ONLY"],
        },
    )

    assert response.status_code == 200
    assert captured["folder_ids"] == []
    assert captured["video_folder_ids"] == [10]
    assert captured["include_bvids"] == {"BV1ONLY"}


@pytest.mark.asyncio
async def test_scoped_build_starts_when_vector_service_is_unavailable(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing embedding key")),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "no-vector-build@example.com", "No Vector")
    knowledge_base = await create_knowledge_base(client, "No Vector KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["rag"].add_video_content(object()) == 0


@pytest.mark.asyncio
async def test_scoped_build_rejects_empty_folder_ids(client, db_session_factory):
    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Folders KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "folder_ids cannot be empty"


@pytest.mark.asyncio
async def test_scoped_build_rejects_other_users_source_binding(
    client,
    db_session_factory,
):
    alice_auth = await register_user(client, "alice@example.com", "Alice")
    alice_binding = await create_source_binding(
        db_session_factory,
        user_id=alice_auth["user"]["id"],
        workspace_id=alice_auth["workspace"]["id"],
    )
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    bob_kb = await create_knowledge_base(client, "Bob Build KB")

    response = await client.post(
        f"/knowledge-bases/{bob_kb['id']}/build",
        json={"source_binding_id": alice_binding.id, "folder_ids": [1]},
    )

    assert response.status_code == 404


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
