import pytest

from app.models import FavoriteFolder, FavoriteVideo, VideoCache


@pytest.mark.asyncio
async def test_protected_knowledge_base_list_requires_login(client):
    response = await client.get("/knowledge-bases")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_create_and_list_own_knowledge_base(client):
    code_resp = await client.post(
        "/system-auth/send-code", json={"email": "alice@example.com"}
    )
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]

    await client.post(
        "/system-auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
            "display_name": "Alice",
            "code": code,
        },
    )

    create_response = await client.post(
        "/knowledge-bases",
        json={"name": "B 站学习库", "description": "课程和访谈"},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "B 站学习库"
    assert created["description"] == "课程和访谈"

    list_response = await client.get("/knowledge-bases")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["B 站学习库"]


def test_scoped_rag_search_requires_workspace_and_knowledge_base_filter():
    from app.services.rag import RAGService

    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["query"] = query
            captured["k"] = k
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    result = service.search_in_knowledge_base(
        "人工智能",
        workspace_id=10,
        knowledge_base_id=20,
        k=3,
    )

    assert result == []
    assert captured["query"] == "人工智能"
    assert captured["k"] == 3
    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
        ]
    }


def test_scoped_rag_search_adds_normalized_bvid_filter():
    from app.services.rag import RAGService

    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    result = service.search_in_knowledge_base(
        "attention",
        workspace_id=10,
        knowledge_base_id=20,
        k=3,
        bvids=["BV1B", "BV1A", "BV1B"],
    )

    assert result == []
    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
            {"bvid": {"$in": ["BV1A", "BV1B"]}},
        ]
    }


@pytest.mark.parametrize("bvids", [None, []])
def test_scoped_rag_search_keeps_legacy_filter_for_empty_scope(bvids):
    from app.services.rag import RAGService

    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    service.search_in_knowledge_base(
        "attention",
        workspace_id=10,
        knowledge_base_id=20,
        bvids=bvids,
    )

    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
        ]
    }


@pytest.mark.asyncio
async def test_delete_knowledge_base_continues_when_vector_cleanup_fails(
    client, monkeypatch
):
    code_resp = await client.post(
        "/system-auth/send-code", json={"email": "delete@example.com"}
    )
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]

    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "delete@example.com",
            "password": "correct horse battery staple",
            "display_name": "Delete User",
            "code": code,
        },
    )
    assert register_response.status_code == 200

    create_response = await client.post(
        "/knowledge-bases",
        json={"name": "Delete Target"},
    )
    assert create_response.status_code == 200
    knowledge_base = create_response.json()

    class BrokenRag:
        def delete_by_knowledge_base(self, knowledge_base_id: int):
            raise RuntimeError("missing api key")

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service", lambda: BrokenRag()
    )

    delete_response = await client.delete(f"/knowledge-bases/{knowledge_base['id']}")
    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload["ok"] is True
    assert payload["deleted_vectors"] == 0
    assert "missing api key" in payload["warning"]

    list_response = await client.get("/knowledge-bases")
    assert list_response.status_code == 200
    assert all(item["id"] != knowledge_base["id"] for item in list_response.json())


@pytest.mark.asyncio
async def test_chat_falls_back_to_database_content_when_vector_retrieval_fails(
    client, db_session_factory, monkeypatch
):
    code_resp = await client.post(
        "/system-auth/send-code", json={"email": "rag-error@example.com"}
    )
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]

    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "rag-error@example.com",
            "password": "correct horse battery staple",
            "display_name": "RAG Error User",
            "code": code,
        },
    )
    assert register_response.status_code == 200
    account_response = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "sk-test-user",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
    )
    assert account_response.status_code == 200

    create_response = await client.post(
        "/knowledge-bases",
        json={"name": "RAG Error KB"},
    )
    assert create_response.status_code == 200
    knowledge_base = create_response.json()

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="rag-error-session",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
            media_id=101,
            title="AI 学习",
            media_count=1,
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid="BV1fallback",
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
            )
        )
        session.add(
            VideoCache(
                bvid="BV1fallback",
                title="DeepSeek 入门",
                content="DeepSeek 可以用于知识库问答。",
                is_processed=True,
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
            )
        )
        await session.commit()

    def broken_rag():
        raise RuntimeError("missing embedding key")

    monkeypatch.setattr("app.routers.knowledge_bases.get_rag_service", broken_rag)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("已根据资料回答：DeepSeek 可以用于知识库问答。", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "hello"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "DeepSeek" in body["answer"]
    assert body["sources"][0]["bvid"] == "BV1fallback"
