import pytest


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
