import json

import pytest

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


@pytest.mark.asyncio
async def test_scoped_chat_web_search_does_not_attach_db_fallback_sources(
    client, monkeypatch
):
    await register_user(client, "web-no-db-source@example.com", "Web No Db Source")
    knowledge_base = await create_knowledge_base(client, "Web No Db Source KB")

    class EmptyRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def fake_load_db_fallback_documents(*args, **kwargs):
        return [
            type(
                "FakeDocument",
                (),
                {
                    "page_content": "Unrelated database fallback content",
                    "metadata": {
                        "bvid": "BVunrelated",
                        "title": "Unrelated DB Source",
                        "url": "https://www.bilibili.com/video/BVunrelated",
                    },
                },
            )()
        ]

    async def fake_complete_with_web(messages, *, question, enable_web_search):
        assert enable_web_search is True
        assert "Unrelated database fallback content" not in json.dumps(
            messages,
            ensure_ascii=False,
        )
        return (
            "answer from web",
            "",
            [
                {
                    "title": "Relevant Web Source",
                    "url": "https://example.com/relevant",
                    "snippet": "Relevant snippet",
                }
            ],
            {
                "status": "success",
                "message": "已使用联网搜索",
                "result_count": 1,
                "results": [
                    {
                        "title": "Relevant Web Source",
                        "url": "https://example.com/relevant",
                        "snippet": "Relevant snippet",
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: EmptyRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        fake_load_db_fallback_documents,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_knowledge_base_answer",
        fake_complete_with_web,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "查外部资料", "web_search": True},
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources == [
        {
            "type": "web",
            "title": "Relevant Web Source",
            "url": "https://example.com/relevant",
        }
    ]


@pytest.mark.asyncio
async def test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty(
    client, monkeypatch
):
    await register_user(client, "empty-vector@example.com", "Empty Vector")
    knowledge_base = await create_knowledge_base(client, "Empty Vector KB")
    captured = {"fallback_called": False}

    class EmptyRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return []

    async def fake_load_db_fallback_documents(*args, **kwargs):
        captured["fallback_called"] = True
        return [
            type(
                "FakeDocument",
                (),
                {
                    "page_content": "Unrelated database fallback content",
                    "metadata": {
                        "bvid": "BVunrelated",
                        "title": "Unrelated DB Source",
                        "url": "https://www.bilibili.com/video/BVunrelated",
                    },
                },
            )()
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: EmptyRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_db_fallback_documents",
        fake_load_db_fallback_documents,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._complete_llm_answer",
        lambda messages: ("不应使用无关兜底资料回答", ""),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "一个与资料无关的问题"},
    )

    assert response.status_code == 200
    assert captured["fallback_called"] is False
    assert response.json()["sources"] == []
    assert "没有找到相关内容" in response.json()["answer"]


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
                        "id": "call_empty_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def __init__(self):
            self.tool_rounds = 0

        def create(self, **kwargs):
            if "tools" in kwargs:
                self.tool_rounds += 1
                if self.tool_rounds == 1:
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
                                            tool_calls=[FakeToolCall()]
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
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
                                        content="answer before fallback"
                                    )
                                },
                            )()
                        ]
                    },
                )()
            captured["final_messages"].append(kwargs["messages"])
            assert "Direct Fallback Web" in json.dumps(
                kwargs["messages"], ensure_ascii=False
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="answer with fallback")},
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

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "只有外部资料的问题"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_web_only"
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
                        "id": "call_web_only",
                        "type": "function",
                        "function": {
                            "name": "web_search",
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
            if "tools" in kwargs:
                if self.calls == 1:
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
                                            tool_calls=[FakeToolCall()]
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content="外部资料答案")},
                            )()
                        ]
                    },
                )()
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="外部资料答案")},
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
