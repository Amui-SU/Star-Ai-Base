import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_scoped_chat_tool_chain_can_fetch_selected_web_page(client, monkeypatch):
    await register_user(client, "web-fetch@example.com", "Web Fetch")
    knowledge_base = await create_knowledge_base(client, "Web Fetch KB")
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
        def __init__(self, name: str, arguments: dict):
            self.name = name
            self.arguments = json.dumps(arguments, ensure_ascii=False)

    class FakeToolCall:
        def __init__(self, call_id: str, name: str, arguments: dict):
            self.id = call_id
            self.function = FakeToolFunction(name, arguments)

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
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in self.tool_calls
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            call_number = len(captured["calls"])
            if call_number == 1:
                assert {tool["function"]["name"] for tool in kwargs["tools"]} == {
                    "web_search",
                    "fetch_web_page",
                }
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[
                                            FakeToolCall(
                                                "call_search",
                                                "web_search",
                                                {"query": "外部查询"},
                                            )
                                        ]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            if call_number == 2:
                assert "搜索结果标题" in json.dumps(
                    kwargs["messages"], ensure_ascii=False
                )
                web_search_tool_message = [
                    message
                    for message in kwargs["messages"]
                    if message["role"] == "tool" and message["name"] == "web_search"
                ][-1]
                assert (
                    json.loads(web_search_tool_message["content"])["source_type"]
                    == "web_search"
                )
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[
                                            FakeToolCall(
                                                "call_fetch",
                                                "fetch_web_page",
                                                {"url": "https://example.com/full"},
                                            )
                                        ]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            assert "网页正文内容" in json.dumps(kwargs["messages"], ensure_ascii=False)
            web_page_tool_message = [
                message
                for message in kwargs["messages"]
                if message["role"] == "tool" and message["name"] == "fetch_web_page"
            ][-1]
            assert (
                json.loads(web_page_tool_message["content"])["source_type"]
                == "web_page"
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="正文增强答案")},
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
        return [
            {
                "title": "搜索结果标题",
                "url": "https://example.com/full",
                "snippet": "搜索摘要",
            }
        ]

    async def fake_fetch_web_page(url, *, max_chars=4000):
        return {
            "url": url,
            "title": "完整网页",
            "content": "网页正文内容",
        }

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
    monkeypatch.setattr(
        "app.routers.knowledge_bases.fetch_web_page",
        fake_fetch_web_page,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查完整网页", "web_search": True},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "正文增强答案"
    assert response.json()["web_search"]["status"] == "success"
    assert len(captured["calls"]) == 3


@pytest.mark.asyncio
async def test_scoped_chat_direct_fetch_tool_reports_page_source(client, monkeypatch):
    await register_user(client, "web-direct-fetch@example.com", "Web Direct Fetch")
    knowledge_base = await create_knowledge_base(client, "Web Direct Fetch KB")

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
        name = "fetch_web_page"
        arguments = json.dumps(
            {"url": "https://example.com/direct"},
            ensure_ascii=False,
        )

    class FakeToolCall:
        id = "call_direct_fetch"
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
                        "id": "call_direct_fetch",
                        "type": "function",
                        "function": {
                            "name": FakeToolFunction.name,
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
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
            assert "直接读取的网页正文" in json.dumps(
                kwargs["messages"],
                ensure_ascii=False,
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="直接网页答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_fetch_web_page(url, *, max_chars=4000):
        return {
            "url": url,
            "title": "直接网页",
            "content": "直接读取的网页正文",
        }

    async def empty_search_web(*args, **kwargs):
        return []

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
    monkeypatch.setattr(
        "app.routers.knowledge_bases.fetch_web_page",
        fake_fetch_web_page,
    )
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={
            "question": "读取这个网页 https://example.com/direct",
            "web_search": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "直接网页答案"
    assert response.json()["sources"][-1] == {
        "type": "web",
        "title": "直接网页",
        "url": "https://example.com/direct",
    }
    assert response.json()["web_search"]["status"] == "success"
    assert response.json()["web_search"]["message"] == "已使用联网搜索"
    assert response.json()["web_search"]["result_count"] == 1
    assert response.json()["web_search"]["queries"] == [
        "读取这个网页 https://example.com/direct"
    ]
    assert response.json()["web_search"]["results"] == [
        {
            "title": "直接网页",
            "url": "https://example.com/direct",
            "snippet": "直接读取的网页正文",
        }
    ]
