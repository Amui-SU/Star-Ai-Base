import pytest

from tests.knowledge_base_web_search_fallback.helpers import (
    create_knowledge_base,
    fake_client,
    fake_completion_response,
    register_user,
    web_search_tool_call,
)


@pytest.mark.asyncio
async def test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits(
    client, monkeypatch
):
    await register_user(client, "web-only@example.com", "Web Only")
    knowledge_base = await create_knowledge_base(client, "Web Only KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if "tools" in kwargs:
                if self.calls == 1:
                    return fake_completion_response(
                        tool_calls=[
                            web_search_tool_call(
                                "call_web_only",
                                "只有外部资料的问题",
                            )
                        ]
                    )
                return fake_completion_response(content="外部资料答案")
            return fake_completion_response(content="外部资料答案")

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        return [
            {
                "title": "外部来源",
                "url": "https://example.com/web-only",
                "snippet": "外部摘要",
            }
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    async def empty_db_fallback(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        empty_db_fallback,
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
        json={"question": "只有外部资料的问题", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "外部资料答案"
    assert captured["search_query"] == "只有外部资料的问题"
    assert response.json()["sources"] == [
        {
            "type": "web",
            "title": "外部来源",
            "url": "https://example.com/web-only",
        }
    ]
    assert response.json()["web_search"]["status"] == "success"
