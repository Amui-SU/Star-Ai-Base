import json

import pytest

from tests.knowledge_base_web_search_fallback.helpers import (
    create_knowledge_base,
    fake_client,
    fake_completion_response,
    fake_document,
    register_user,
    web_search_tool_call,
)


@pytest.mark.asyncio
async def test_scoped_chat_adds_initial_web_sources_to_first_answer_context(
    client, monkeypatch
):
    await register_user(
        client, "web-fallback-answer@example.com", "Web Fallback Answer"
    )
    knowledge_base = await create_knowledge_base(client, "Web Fallback Answer KB")
    captured = {"queries": [], "final_messages": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                fake_document(
                    "Knowledge context.",
                    {"bvid": "BV1KB", "title": "Knowledge Source"},
                )
            ]

    class FakeCompletions:
        def __init__(self):
            self.tool_rounds = 0

        def create(self, **kwargs):
            if "tools" in kwargs:
                self.tool_rounds += 1
                if self.tool_rounds == 1:
                    return fake_completion_response(
                        tool_calls=[
                            web_search_tool_call(
                                "call_empty_search",
                                "model query with no hits",
                            )
                        ]
                    )
                return fake_completion_response(content="answer before fallback")
            captured["final_messages"].append(kwargs["messages"])
            assert "Direct Fallback Web" in json.dumps(
                kwargs["messages"], ensure_ascii=False
            )
            return fake_completion_response(content="answer with fallback")

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

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._get_llm_client",
        lambda config: fake_client(FakeCompletions()),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "original user question", "web_search": True},
    )

    assert response.status_code == 200
    assert captured["queries"] == ["original user question", "model query with no hits"]
    assert captured["final_messages"] == []
    assert response.json()["answer"] == "answer before fallback"
    assert response.json()["web_search"]["status"] == "success"
    assert {
        "type": "web",
        "title": "Direct Fallback Web",
        "url": "https://example.com/direct-fallback",
    } in response.json()["sources"]
