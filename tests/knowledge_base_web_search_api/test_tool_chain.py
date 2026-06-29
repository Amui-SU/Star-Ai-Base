import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


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
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库资料",
                        "metadata": {
                            "bvid": "BV1KB",
                            "title": "Knowledge Source",
                            "url": "https://www.bilibili.com/video/BV1KB",
                        },
                    },
                )()
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
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge context.",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
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
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库资料",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "模型改写后的外部查询"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_search_1"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_search_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert any(message["role"] == "tool" for message in kwargs["messages"])
            assert "搜索结果标题" in json.dumps(kwargs["messages"], ensure_ascii=False)
            if "tools" in kwargs:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content="工具链答案")},
                            )()
                        ]
                    },
                )()
            assert "tools" not in kwargs
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="工具链答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

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
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Knowledge content",
                        "metadata": {"bvid": "BV1KB", "title": "Knowledge Source"},
                    },
                )()
            ]

    class FakeToolFunction:
        name = "web_search"
        arguments = {"search_query": "aliased external query"}

    class FakeToolCall:
        id = "call_alias_search"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_alias_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert "Alias Result" in json.dumps(kwargs["messages"], ensure_ascii=False)
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="alias answer")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

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
        json={"question": "Need external data", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "alias answer"
    assert captured["search_query"] == "aliased external query"
    assert response.json()["web_search"]["status"] == "success"
