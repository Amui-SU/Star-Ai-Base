import pytest

from app.models import SourceBinding


async def register_user(client, email: str, display_name: str) -> dict:
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_knowledge_base(client, name: str = "Scoped KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "scope test"},
    )
    assert response.status_code == 200
    return response.json()


async def create_source_binding(
    db_session_factory,
    *,
    user_id: int,
    workspace_id: int,
    status: str = "active",
) -> SourceBinding:
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=user_id,
            workspace_id=workspace_id,
            source_type="bilibili",
            external_account_id=f"mid-{user_id}-{workspace_id}-{status}",
            external_account_name="Bilibili Account",
            status=status,
        )
        session.add(binding)
        await session.commit()
        await session.refresh(binding)
        return binding


@pytest.mark.asyncio
async def test_scoped_stats_requires_login(client):
    response = await client.get("/knowledge-bases/1/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scoped_stats_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/stats")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_search_uses_workspace_and_knowledge_base_filter(
    client,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Search KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "chunk text",
                        "metadata": {
                            "bvid": "BV1xx411c7mD",
                            "title": "Test Video",
                            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "人工智能", "k": 3},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Test Video"
    assert captured == {
        "query": "人工智能",
        "workspace_id": knowledge_base["workspace_id"],
        "knowledge_base_id": knowledge_base["id"],
        "k": 3,
    }


@pytest.mark.asyncio
async def test_scoped_chat_uses_scoped_retrieval(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Chat KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Python is a programming language.",
                        "metadata": {
                            "bvid": "BV1py411c7mD",
                            "title": "Python Intro",
                            "url": "https://www.bilibili.com/video/BV1py411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "What is Python?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["answer"]
    assert body["sources"][0]["title"] == "Python Intro"
    assert captured["workspace_id"] == knowledge_base["workspace_id"]
    assert captured["knowledge_base_id"] == knowledge_base["id"]


@pytest.mark.asyncio
async def test_scoped_chat_stream_requires_owned_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice Stream KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.post(
        f"/knowledge-bases/{alice_kb['id']}/chat/stream",
        json={"question": "hello"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_chat_stream_returns_answer_for_owner(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Owner Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Streamed answer chunk.",
                        "metadata": {
                            "bvid": "BV1st411c7mD",
                            "title": "Stream Intro",
                            "url": "https://www.bilibili.com/video/BV1st411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "stream please"},
    )

    assert response.status_code == 200
    assert "Streamed answer chunk." in response.text
    assert "[[SOURCES_JSON]]" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_json_encodes_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Thinking Stream KB")

    async def fake_chat_with_knowledge_base(payload, knowledge_base, current_workspace):
        from app.models import ChatResponse

        return ChatResponse(answer="done", sources=[], thinking="思考")

    monkeypatch.setattr(
        "app.routers.knowledge_bases.chat_with_knowledge_base",
        fake_chat_with_knowledge_base,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "show thinking"},
    )

    assert response.status_code == 200
    assert '[[THINKING_JSON]]"思考"' in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_emits_empty_sources_trailer(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
        ):
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "nothing here"},
    )

    assert response.status_code == 200
    assert "[[SOURCES_JSON]][]" in response.text


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
async def test_scoped_build_records_scope_metadata(client, db_session_factory):
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
