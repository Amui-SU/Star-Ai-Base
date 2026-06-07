import pytest


async def register_user(client, email: str, display_name: str) -> None:
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
        },
    )
    assert response.status_code == 200


async def create_knowledge_base(client, name: str = "Scoped KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "scope test"},
    )
    assert response.status_code == 200
    return response.json()


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
