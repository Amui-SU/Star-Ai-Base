import pytest

from app.services.knowledge_web_search_tools import (
    FETCH_WEB_PAGE_CONTEXT_CHARS,
    execute_fetch_web_page_tool,
    execute_web_search_tool,
)


@pytest.mark.asyncio
async def test_execute_web_search_tool_passes_provider_key_and_records_results():
    calls = []

    async def search_web(
        query, *, diagnostics=None, provider=None, tavily_api_key=None
    ):
        calls.append(
            {
                "query": query,
                "diagnostics": diagnostics,
                "provider": provider,
                "tavily_api_key": tavily_api_key,
            }
        )
        return [
            {
                "title": "Result",
                "url": "https://example.com/result",
                "snippet": query,
            }
        ]

    web_results = []
    state = {
        "provider": "tavily",
        "tavily_api_key": "user-key",
    }

    result = await execute_web_search_tool(
        {"query": "  知识库   维护  "},
        web_results,
        state,
        search_web=search_web,
    )

    assert result["query"] == "知识库 维护"
    assert result["results"] == web_results
    assert web_results == [
        {
            "title": "Result",
            "url": "https://example.com/result",
            "snippet": "知识库 维护",
        }
    ]
    assert calls == [
        {
            "query": "知识库 维护",
            "diagnostics": [],
            "provider": "tavily",
            "tavily_api_key": "user-key",
        }
    ]
    assert state["attempted"] is True
    assert state["query_log"] == ["知识库 维护"]


@pytest.mark.asyncio
async def test_execute_fetch_web_page_tool_enforces_limit_and_appends_source():
    calls = []

    async def fetch_web_page(url, *, max_chars):
        calls.append({"url": url, "max_chars": max_chars})
        return {
            "url": url,
            "title": "Fetched",
            "content": "Fetched content",
        }

    web_results = []
    state = {}

    result = await execute_fetch_web_page_tool(
        {"url": "https://example.com/page"},
        web_results,
        state,
        fetch_web_page=fetch_web_page,
    )
    limited = await execute_fetch_web_page_tool(
        {"url": "https://example.com/second"},
        web_results,
        state,
        fetch_web_page=fetch_web_page,
    )

    assert result["title"] == "Fetched"
    assert web_results == [
        {
            "title": "Fetched",
            "url": "https://example.com/page",
            "snippet": "Fetched content",
        }
    ]
    assert calls == [
        {
            "url": "https://example.com/page",
            "max_chars": FETCH_WEB_PAGE_CONTEXT_CHARS,
        }
    ]
    assert limited["error"] == "fetch_limit_exceeded"
    assert limited["message"] == "网页读取次数已达到上限"
    assert state["fetch_count"] == 1
    assert state["errors"] == [
        {"source": "web_page", "message": "网页读取次数已达到上限"}
    ]
