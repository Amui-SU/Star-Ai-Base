import json

import pytest


@pytest.mark.asyncio
async def test_initial_web_context_is_not_duplicated_after_tool_run(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {}

    async def fake_search_web(query, *, max_results=3):
        return [
            {
                "title": "Initial Web Result",
                "url": "https://example.com/initial",
                "snippet": "Initial snippet",
            }
        ]

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        captured["messages"] = messages
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    assert len(web_results) == 1
    assert (
        json.dumps(captured["messages"], ensure_ascii=False).count("Initial Web Result")
        == 1
    )
    assert (
        json.dumps(tool_run.messages, ensure_ascii=False).count("Initial Web Result")
        == 1
    )


@pytest.mark.asyncio
async def test_initial_web_search_no_results_is_visible_to_model(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {}

    async def empty_search_web(*args, **kwargs):
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        captured["messages"] = messages
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", empty_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    _tool_run, web_results, state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    serialized_messages = json.dumps(captured["messages"], ensure_ascii=False)
    assert web_results == []
    assert state["attempted"] is True
    assert "初始联网搜索未返回可用结果" in serialized_messages
    assert "不要声称已获得外部网页资料" in serialized_messages
    assert "可以基于模型已有通用知识回答" in serialized_messages
    assert "不要把通用知识伪装成检索资料" in serialized_messages


@pytest.mark.asyncio
async def test_web_search_tool_run_uses_request_provider(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"providers": []}

    async def fake_search_web(query, *, max_results=3, diagnostics=None, provider=None):
        captured["providers"].append(provider)
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "tool query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    await _prepare_web_search_tool_run(
        [{"role": "user", "content": "question"}],
        question="initial query",
        provider="tavily",
    )

    assert captured["providers"] == ["tavily", "tavily"]


@pytest.mark.asyncio
async def test_web_search_tool_run_uses_tavily_api_key(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"keys": []}

    async def fake_search_web(
        query,
        *,
        max_results=3,
        diagnostics=None,
        provider=None,
        tavily_api_key=None,
    ):
        captured["keys"].append(tavily_api_key)
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "tool query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    await _prepare_web_search_tool_run(
        [{"role": "user", "content": "question"}],
        question="initial query",
        provider="tavily",
        tavily_api_key="user-tavily-key",
    )

    assert captured["keys"] == ["user-tavily-key", "user-tavily-key"]


@pytest.mark.asyncio
async def test_initial_web_search_diagnostics_are_reported_when_search_fails(
    monkeypatch,
):
    from app.routers.knowledge_bases import (
        _prepare_web_search_tool_run,
        _status_from_web_search_state,
    )

    async def failing_search_web(*args, **kwargs):
        kwargs["diagnostics"].append(
            {
                "provider": "duckduckgo",
                "status": "failed",
                "message": "proxy connection refused",
                "proxy_configured": False,
            }
        )
        return []

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", failing_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    _tool_run, web_results, state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )

    status = _status_from_web_search_state(web_results, state)

    assert status["status"] == "no_results"
    assert status["errors"] == [
        {
            "source": "duckduckgo",
            "query": "question",
            "message": "proxy connection refused（未配置 HTTP_PROXY）",
        }
    ]


@pytest.mark.asyncio
async def test_only_new_tool_results_are_appended_after_initial_web_context(
    monkeypatch,
):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    async def fake_search_web(query, *, max_results=3):
        if query == "question":
            return [
                {
                    "title": "Initial Web Result",
                    "url": "https://example.com/initial",
                    "snippet": "Initial snippet",
                }
            ]
        return [
            {
                "title": "Extra Web Result",
                "url": "https://example.com/extra",
                "snippet": "Extra snippet",
            }
        ]

    async def fake_prepare_llm_messages_with_tools(messages, **kwargs):
        await kwargs["tool_handlers"]["web_search"]({"query": "extra query"})
        from app.routers.chat import LLMToolRunResult

        return LLMToolRunResult(messages=messages, answer="answer", thinking="")

    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)
    monkeypatch.setattr(
        "app.routers.knowledge_bases._prepare_llm_messages_with_tools",
        fake_prepare_llm_messages_with_tools,
    )

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
    )
    serialized_messages = json.dumps(tool_run.messages, ensure_ascii=False)

    assert len(web_results) == 2
    assert serialized_messages.count("Initial Web Result") == 1
    assert serialized_messages.count("Extra Web Result") == 1


@pytest.mark.asyncio
async def test_tool_web_results_remove_initial_no_results_instruction(monkeypatch):
    from app.routers.knowledge_bases import _prepare_web_search_tool_run

    captured = {"calls": [], "second_call_messages": []}

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "tool query"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_search"
        function = FakeToolFunction()

    class FakeMessage:
        reasoning_content = ""

        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_search",
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
                captured["first_call_messages"] = kwargs["messages"]
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
            captured["second_call_messages"] = kwargs["messages"]
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type("Choice", (), {"message": FakeMessage(content="answer")})()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_search_web(query, *, max_results=3):
        if query == "question":
            return []
        return [
            {
                "title": "Tool Web Result",
                "url": "https://example.com/tool",
                "snippet": "Tool snippet",
            }
        ]

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
    monkeypatch.setattr("app.routers.knowledge_bases.search_web", fake_search_web)

    tool_run, web_results, _state = await _prepare_web_search_tool_run(
        [{"role": "user", "content": "知识库资料\n\n问题：question"}],
        question="question",
        provider="tavily",
    )
    serialized_second_call = json.dumps(
        captured["second_call_messages"],
        ensure_ascii=False,
    )
    serialized_final_messages = json.dumps(tool_run.messages, ensure_ascii=False)

    assert len(web_results) == 1
    assert "联网搜索资料" in serialized_second_call
    assert "Tool Web Result" in serialized_second_call
    assert "不要声称已获得外部网页资料" not in serialized_second_call
    assert "联网搜索资料" in serialized_final_messages
    assert "不要声称已获得外部网页资料" not in serialized_final_messages
