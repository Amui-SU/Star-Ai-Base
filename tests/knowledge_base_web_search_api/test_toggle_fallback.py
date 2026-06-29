import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_scoped_chat_does_not_web_search_by_default(client, monkeypatch):
    await register_user(client, "no-web-search@example.com", "No Web Search")
    knowledge_base = await create_knowledge_base(client, "No Web Search KB")

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

    async def fail_search_web(*args, **kwargs):
        raise AssertionError("web search should not run when the toggle is off")

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fail_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("知识库答案", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "只看知识库"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "知识库答案"


@pytest.mark.asyncio
async def test_scoped_chat_forces_web_search_when_enabled_without_model_tool_call(
    client, monkeypatch
):
    await register_user(client, "web-unused@example.com", "Web Unused")
    knowledge_base = await create_knowledge_base(client, "Web Unused KB")
    captured = {"calls": [], "queries": []}

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
        content = "未使用工具的答案"
        reasoning_content = ""
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            assert kwargs["tools"][0]["function"]["name"] == "web_search"
            assert "Forced Web Result" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
            assert "Forced snippet" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
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

    async def fake_search_web(query, *, max_results=3):
        captured["queries"].append(query)
        return [
            {
                "title": "Forced Web Result",
                "url": "https://example.com/forced",
                "snippet": "Forced snippet",
            }
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "未使用工具的答案"
    assert captured["queries"][0] == "查外部资料"
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == ["查外部资料"]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "Forced Web Result",
            "url": "https://example.com/forced",
            "snippet": "Forced snippet",
        }
    ]
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "Forced Web Result",
        "url": "https://example.com/forced",
    }
    assert len(captured["calls"]) == 1
