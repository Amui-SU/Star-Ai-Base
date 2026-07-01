import pytest

from tests.knowledge_base_web_search_api.helpers import (
    create_knowledge_base,
    fake_document,
    register_user,
)


@pytest.mark.asyncio
async def test_scoped_chat_lets_llm_call_web_search_tool_when_enabled(
    client, monkeypatch
):
    await register_user(client, "web-search@example.com", "Web Search")
    knowledge_base = await create_knowledge_base(client, "Web Search KB")
    captured = {}

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
                fake_document(
                    "知识库资料",
                    {
                        "bvid": "BV1KB",
                        "title": "Knowledge Source",
                        "url": "https://www.bilibili.com/video/BV1KB",
                    },
                )
            ]

    async def fake_search_web(query, *, max_results=3):
        captured["query"] = query
        captured["max_results"] = max_results
        return [
            {
                "title": "外部资料标题",
                "url": "https://example.com/news",
                "snippet": "外部资料摘要",
            }
        ]

    async def fake_complete_with_tools(messages, *, question, enable_web_search):
        captured["question"] = question
        captured["enable_web_search"] = enable_web_search
        captured["messages"] = messages
        return (
            "联网答案",
            "",
            [
                {
                    "title": "外部资料标题",
                    "url": "https://example.com/news",
                    "snippet": "外部资料摘要",
                }
            ],
            {
                "status": "success",
                "message": "已使用联网搜索",
                "result_count": 1,
            },
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        fake_complete_with_tools,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "今天有什么新进展？", "web_search": True},
    )

    assert response.status_code == 200
    assert "query" not in captured
    assert captured["enable_web_search"] is True
    assert "外部资料标题" not in str(captured["messages"])
    assert "外部资料摘要" not in str(captured["messages"])
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "外部资料标题",
        "url": "https://example.com/news",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1


@pytest.mark.asyncio
async def test_scoped_chat_reports_socks_dependency_failure(client, monkeypatch):
    await register_user(client, "web-socks-failure@example.com", "Web Socks Failure")
    knowledge_base = await create_knowledge_base(client, "Web Socks Failure KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                fake_document(
                    "Knowledge context.",
                    {"bvid": "BV1KB", "title": "Knowledge Source"},
                )
            ]

    async def failing_complete(*args, **kwargs):
        raise RuntimeError(
            "Using SOCKS proxy, but the 'socksio' package is not installed. "
            "Make sure to install httpx using `pip install httpx[socks]`."
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        failing_complete,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    web_search = response.json()["web_search"]
    assert web_search["status"] == "failed"
    assert "联网搜索代理依赖缺失" in web_search["message"]
    assert "当前模型不支持联网搜索工具调用" not in web_search["message"]
    assert web_search["errors"][0]["source"] == "web_search"
    assert "socksio" in web_search["errors"][0]["message"]
