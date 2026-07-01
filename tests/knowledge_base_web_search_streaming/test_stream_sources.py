import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base
from tests.test_knowledge_base_scoping import register_user


@pytest.mark.asyncio
async def test_scoped_chat_stream_adds_web_sources_from_initial_search(
    client, monkeypatch
):
    await register_user(
        client, "web-stream-fallback@example.com", "Web Stream Fallback"
    )
    knowledge_base = await create_knowledge_base(client, "Web Stream Fallback KB")
    captured = {"queries": [], "stream_messages": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge context.",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "model query with no hits"})

    class FakeToolCall:
        id = "call_empty_search"
        function = FakeToolFunction()

    class FakeToolMessage:
        content = ""
        reasoning_content = ""
        tool_calls = [FakeToolCall()]

        def model_dump(self, exclude_none=True):
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_empty_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ],
            }

    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeToolMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        captured["queries"].append(query)
        if query == "original user question":
            return [
                {
                    "title": "Direct Fallback Web",
                    "url": "https://example.com/direct-fallback",
                    "snippet": "Direct fallback snippet",
                }
            ]
        return []

    def fake_stream_llm_events(messages):
        captured["stream_messages"].append(messages)
        assert "Direct Fallback Web" in json.dumps(messages, ensure_ascii=False)
        yield "answer", "stream answer with fallback web"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._get_llm_client", lambda config: fake_client
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "original user question", "web_search": True},
    )

    assert response.status_code == 200
    assert captured["queries"] == ["original user question", "model query with no hits"]
    assert '"status": "success"' in response.text
    assert '"type": "web"' in response.text
    assert "Direct Fallback Web" in response.text
    assert "https://example.com/direct-fallback" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_final_stream_after_tool_decision(
    client, monkeypatch
):
    await register_user(client, "web-stream-unused@example.com", "Web Stream Unused")
    knowledge_base = await create_knowledge_base(client, "Web Stream Unused KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库资料",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeMessage:
        content = "无需联网的流式答案"
        reasoning_content = "先判断无需搜索"
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["tools"][0]["function"]["name"] == "web_search"
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    captured = {"stream_messages": None}

    def fake_stream_llm_events(messages):
        captured["stream_messages"] = messages
        yield "thinking", "实时思考"
        yield "answer", "实时流式答案"

    async def empty_search_web(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._get_llm_client", lambda config: fake_client
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    assert "实时流式答案" in response.text
    assert '[[THINKING_DELTA]]"实时思考"' in response.text
    assert "无需联网的流式答案" not in response.text
    assert captured["stream_messages"] is not None
    assert "[[WEB_SEARCH_JSON]]" in response.text
    assert '"status": "no_results"' in response.text
