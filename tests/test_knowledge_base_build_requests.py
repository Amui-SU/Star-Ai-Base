import pytest

from tests.test_knowledge_base_scoping import (
    create_knowledge_base,
    create_source_binding,
    register_user,
)


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
