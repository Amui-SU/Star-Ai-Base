import types

import pytest

from app.services.knowledge_base_web_search_compat import (
    build_web_search_orchestration_compat,
)


@pytest.mark.asyncio
async def test_compat_execute_web_search_tool_uses_router_module_search_web():
    calls = []

    async def search_web(query, **kwargs):
        calls.append({"query": query, "kwargs": kwargs})
        return [{"title": "Result", "url": "https://example.com", "snippet": query}]

    module = types.SimpleNamespace(search_web=search_web)
    compat = build_web_search_orchestration_compat(module)

    web_results = []
    state = {"provider": "html", "tavily_api_key": None}
    result = await compat["_execute_web_search_tool"](
        {"query": "知识库维护"},
        web_results,
        state,
    )

    assert calls == [
        {
            "query": "知识库维护",
            "kwargs": {
                "diagnostics": [],
                "provider": "html",
                "tavily_api_key": None,
            },
        }
    ]
    assert result["results"] == web_results
    assert web_results[0]["title"] == "Result"


@pytest.mark.asyncio
async def test_compat_prepare_web_search_tool_run_uses_router_module_tool_helpers():
    async def search_web(query, **kwargs):
        return [{"title": "Search", "url": "https://example.com", "snippet": query}]

    async def fetch_web_page(url, **kwargs):
        return {"url": url, "title": "Fetched", "content": "Fetched content"}

    async def prepare_llm_messages_with_tools(messages, **kwargs):
        assert kwargs["tool_handlers"]["web_search"]
        assert kwargs["tool_handlers"]["fetch_web_page"]
        return types.SimpleNamespace(
            answer="answer",
            thinking="thinking",
            messages=messages,
        )

    module = types.SimpleNamespace(
        search_web=search_web,
        fetch_web_page=fetch_web_page,
        _prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
    )
    compat = build_web_search_orchestration_compat(module)

    tool_run, web_results, state = await compat["_prepare_web_search_tool_run"](
        [{"role": "user", "content": "question"}],
        question="question",
    )

    assert tool_run.answer == "answer"
    assert web_results
    assert state["attempted"] is True
