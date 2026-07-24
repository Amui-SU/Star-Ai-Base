"""Knowledge-base web-search tool handlers."""

from collections.abc import Awaitable, Callable

from loguru import logger

from app.services.knowledge_base_presenters import supports_keyword_argument
from app.services.llm_errors import classify_upstream_error
from app.services.knowledge_web_search import (
    append_web_result,
    append_web_search_diagnostics,
    normalize_web_search_query,
)
from app.services.web_search import fetch_web_page as default_fetch_web_page
from app.services.web_search import search_web as default_search_web

MAX_FETCH_WEB_PAGE_CALLS = 1
FETCH_WEB_PAGE_CONTEXT_CHARS = 2000

SearchWeb = Callable[..., Awaitable[list[dict[str, str]]]]
FetchWebPage = Callable[..., Awaitable[dict]]


async def execute_web_search_tool(
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
    *,
    search_web: SearchWeb = default_search_web,
) -> dict:
    state["attempted"] = True
    query = normalize_web_search_query(str(arguments.get("query") or "").strip())
    if not query:
        state.setdefault("errors", []).append(
            {"source": "web_search", "message": "搜索关键词为空"}
        )
        return {
            "source_type": "web_search",
            "query": query,
            "results": [],
            "message": "搜索关键词为空",
        }
    search_queries = state.setdefault("queries", set())
    query_key = query.casefold()
    if query_key in search_queries:
        return {
            "source_type": "web_search",
            "query": query,
            "results": [],
            "message": "Duplicate web search skipped.",
        }
    search_queries.add(query_key)
    state.setdefault("query_log", []).append(query)
    try:
        diagnostics: list[dict] = []
        supports_diagnostics = supports_keyword_argument(search_web, "diagnostics")
        supports_provider = supports_keyword_argument(search_web, "provider")
        supports_tavily_api_key = supports_keyword_argument(
            search_web,
            "tavily_api_key",
        )
        search_kwargs = {}
        if supports_diagnostics:
            search_kwargs["diagnostics"] = diagnostics
        if supports_provider:
            search_kwargs["provider"] = state.get("provider")
        if supports_tavily_api_key:
            search_kwargs["tavily_api_key"] = state.get("tavily_api_key")
        results = await search_web(query, **search_kwargs)
    except Exception as exc:
        state["failed"] = True
        state.setdefault("errors", []).append(
            {"source": "web_search", "query": query, "message": "联网搜索失败"}
        )
        failure = classify_upstream_error(exc)
        logger.warning(failure.log_message("联网搜索工具调用失败，将仅使用知识库回答"))
        return {
            "source_type": "web_search",
            "query": query,
            "results": [],
            "error": "search_failed",
            "message": "联网搜索失败",
        }
    if diagnostics and not results:
        append_web_search_diagnostics(state, query, diagnostics)
    for result in results:
        append_web_result(web_results, result)
    return {"source_type": "web_search", "query": query, "results": results}


async def execute_fetch_web_page_tool(
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
    *,
    fetch_web_page: FetchWebPage = default_fetch_web_page,
) -> dict:
    state["attempted"] = True
    fetch_count = state.setdefault("fetch_count", 0)
    if fetch_count >= MAX_FETCH_WEB_PAGE_CALLS:
        state.setdefault("errors", []).append(
            {"source": "web_page", "message": "网页读取次数已达到上限"}
        )
        return {
            "source_type": "web_page",
            "url": str(arguments.get("url") or "").strip(),
            "title": "",
            "content": "",
            "error": "fetch_limit_exceeded",
            "message": "网页读取次数已达到上限",
        }
    url = str(arguments.get("url") or "").strip()
    if not url:
        state.setdefault("errors", []).append(
            {"source": "web_page", "message": "URL 为空"}
        )
        return {
            "source_type": "web_page",
            "url": url,
            "title": "",
            "content": "",
            "message": "URL 为空",
        }
    state["fetch_count"] = fetch_count + 1
    result = await fetch_web_page(url, max_chars=FETCH_WEB_PAGE_CONTEXT_CHARS)
    if result.get("error"):
        if result["error"] == "fetch_failed":
            result = {**result, "message": "网页读取失败"}
        state["failed"] = True
        state.setdefault("errors", []).append(
            {
                "source": "web_page",
                "url": url,
                "message": result.get("message")
                or result.get("error")
                or "网页读取失败",
            }
        )
    else:
        append_web_result(
            web_results,
            {
                "title": result.get("title") or url,
                "url": result.get("url") or url,
                "snippet": result.get("content") or "",
            },
        )
    return {"source_type": "web_page", **result}
