import json

import pytest

from tests.knowledge_base_web_search_api.helpers import (
    create_knowledge_base,
    fake_client,
    fake_completion_response,
    fake_document,
    register_user,
    web_search_tool_call,
)


@pytest.mark.asyncio
async def test_scoped_chat_web_search_tool_chain_executes_model_requested_query(
    client, monkeypatch
):
    await register_user(client, "web-tool-chain@example.com", "Web Tool Chain")
    knowledge_base = await create_knowledge_base(client, "Web Tool Chain KB")
    captured = {"calls": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                fake_document(
                    "知识库资料",
                    {"bvid": "BV1KB", "title": "Knowledge Source"},
                )
            ]

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                return fake_completion_response(
                    tool_calls=[
                        web_search_tool_call(
                            "call_search_1",
                            {"query": "模型改写后的外部查询"},
                        )
                    ]
                )
            assert any(message["role"] == "tool" for message in kwargs["messages"])
            assert "搜索结果标题" in json.dumps(kwargs["messages"], ensure_ascii=False)
            return fake_completion_response(content="工具链答案")

    fake_client_instance = fake_client(FakeCompletions())

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        captured["max_results"] = max_results
        return [
            {
                "title": "搜索结果标题",
                "url": "https://example.com/tool",
                "snippet": "搜索结果摘要",
            }
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._get_llm_client",
        lambda config: fake_client_instance,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "今天有什么新进展？", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "工具链答案"
    assert captured["search_query"] == "模型改写后的外部查询"
    assert captured["max_results"] == 3
    assert len(captured["calls"]) == 2
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "搜索结果标题",
        "url": "https://example.com/tool",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == [
        "今天有什么新进展？",
        "模型改写后的外部查询",
    ]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "搜索结果标题",
            "url": "https://example.com/tool",
            "snippet": "搜索结果摘要",
        }
    ]


@pytest.mark.asyncio
async def test_scoped_chat_web_search_tool_accepts_query_alias_arguments(
    client, monkeypatch
):
    await register_user(client, "web-tool-alias@example.com", "Web Tool Alias")
    knowledge_base = await create_knowledge_base(client, "Web Tool Alias KB")
    captured = {"calls": []}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                fake_document(
                    "Knowledge content",
                    {"bvid": "BV1KB", "title": "Knowledge Source"},
                )
            ]

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                return fake_completion_response(
                    tool_calls=[
                        web_search_tool_call(
                            "call_alias_search",
                            {"search_query": "aliased external query"},
                            encode_json=False,
                        )
                    ]
                )
            assert "Alias Result" in json.dumps(kwargs["messages"], ensure_ascii=False)
            return fake_completion_response(content="alias answer")

    fake_client_instance = fake_client(FakeCompletions())

    async def fake_search_web(query, *, max_results=3):
        captured["search_query"] = query
        return [
            {
                "title": "Alias Result",
                "url": "https://example.com/alias",
                "snippet": "Alias snippet",
            }
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._get_llm_client",
        lambda config: fake_client_instance,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {"thinking_config": {}},
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "Need external data", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "alias answer"
    assert captured["search_query"] == "aliased external query"
    assert response.json()["web_search"]["status"] == "success"
