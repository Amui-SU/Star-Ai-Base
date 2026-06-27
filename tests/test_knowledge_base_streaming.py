import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


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
            bvids=None,
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

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "context",
                        "metadata": {"bvid": "BV1", "title": "Source"},
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        yield "thinking", "思考"
        yield "answer", "done"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "show thinking"},
    )

    assert response.status_code == 200
    assert '[[THINKING_JSON]]"思考"' in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_configured_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    accounts_response = await client.get("/api-accounts")
    assert accounts_response.status_code == 200
    account_id = accounts_response.json()[0]["id"]
    update_response = await client.patch(
        f"/api-accounts/{account_id}",
        json={"thinking_config": {"thinking": {"type": "enabled"}}},
    )
    assert update_response.status_code == 200
    knowledge_base = await create_knowledge_base(client, "Native Thinking KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库上下文",
                        "metadata": {
                            "bvid": "BV1thinking",
                            "title": "Thinking Source",
                            "url": "https://www.bilibili.com/video/BV1thinking",
                        },
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        captured["messages"] = messages
        yield "thinking", "先分析"
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )
    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "请回答"},
    )

    assert response.status_code == 200
    assert "知识库上下文" in str(captured["messages"])
    assert "原生 reasoning/thinking" in str(captured["messages"])
    assert '[[THINKING_DELTA]]"先分析"' in response.text
    assert "模型答案" in response.text


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
            bvids=None,
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
