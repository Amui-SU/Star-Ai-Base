import pytest

from tests.test_knowledge_base_scoping import (
    create_knowledge_base,
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
