import asyncio
from collections.abc import Awaitable, Callable

import httpx
from loguru import logger

from app.config import settings
from app.services.web_page_fetcher import truncate_text
from app.services.web_search_parsers import (
    DuckDuckGoResultParser,
    SogouResultParser,
    YahooResultParser,
)
from app.services.web_search_safety import is_blocked_search_result_url

MAX_SEARCH_TITLE_CHARS = 180
MAX_SEARCH_SNIPPET_CHARS = 600
SEARCH_PROVIDERS = ("tavily", "duckduckgo", "yahoo", "sogou")

SearchResult = dict[str, str]
SearchResults = list[SearchResult]
Diagnostics = list[dict] | None
SearchNormalizer = Callable[[SearchResults, int], Awaitable[SearchResults]]


async def cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    pending_tasks = [task for task in tasks if not task.done()]
    if not pending_tasks:
        return
    for task in pending_tasks:
        task.cancel()
    await asyncio.gather(*pending_tasks, return_exceptions=True)


def sort_provider_diagnostics(diagnostics: Diagnostics) -> None:
    if diagnostics is None:
        return
    provider_order = {
        provider: index for index, provider in enumerate(SEARCH_PROVIDERS)
    }
    diagnostics.sort(
        key=lambda item: provider_order.get(
            str(item.get("provider") or ""),
            len(provider_order),
        )
    )


def append_missing_tavily_key_diagnostic(diagnostics: Diagnostics) -> None:
    if diagnostics is None:
        return
    diagnostics.append(
        {
            "provider": "tavily",
            "status": "failed",
            "error": "missing_api_key",
            "message": "TAVILY_API_KEY is not configured",
            "proxy_configured": bool(settings.http_proxy.strip()),
        }
    )


async def search_html_providers(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: Diagnostics = None,
    duckduckgo_searcher=None,
    yahoo_searcher=None,
    sogou_searcher=None,
) -> SearchResults:
    combined: SearchResults = []
    seen_urls: set[str] = set()
    provider_tasks = [
        asyncio.create_task(
            try_search_provider(
                provider,
                searcher,
                client,
                query,
                max_results=max_results,
                diagnostics=diagnostics,
            )
        )
        for provider, searcher in (
            ("duckduckgo", duckduckgo_searcher or search_duckduckgo),
            ("yahoo", yahoo_searcher or search_yahoo),
            ("sogou", sogou_searcher or search_sogou),
        )
    ]
    try:
        for provider_task in asyncio.as_completed(provider_tasks):
            provider_results = await provider_task
            for result in provider_results:
                url = (result.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                combined.append(result)
                if len(combined) >= max_results:
                    await cancel_pending_tasks(provider_tasks)
                    sort_provider_diagnostics(diagnostics)
                    return combined
    finally:
        await cancel_pending_tasks(provider_tasks)
    sort_provider_diagnostics(diagnostics)
    return combined


async def try_search_provider(
    provider: str,
    searcher,
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: Diagnostics = None,
    **search_kwargs,
) -> SearchResults:
    try:
        results = await searcher(
            client,
            query,
            max_results=max_results,
            **search_kwargs,
        )
    except Exception as exc:
        logger.debug(f"联网搜索源 {provider} 查询失败，继续尝试备用源: {exc}")
        if diagnostics is not None:
            diagnostics.append(
                {
                    "provider": provider,
                    "status": "failed",
                    "error": exc.__class__.__name__,
                    "message": truncate_text(str(exc), 240) or "搜索源请求失败",
                    "proxy_configured": bool(settings.http_proxy.strip()),
                }
            )
        return []
    if diagnostics is not None:
        diagnostics.append(
            {
                "provider": provider,
                "status": "success" if results else "empty",
                "result_count": len(results),
                "message": "搜索源返回结果" if results else "搜索源返回空结果",
                "proxy_configured": bool(settings.http_proxy.strip()),
            }
        )
    return results


async def search_duckduckgo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    normalize_results: SearchNormalizer | None = None,
) -> SearchResults:
    response = await client.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
    )
    response.raise_for_status()

    parser = DuckDuckGoResultParser()
    parser.feed(response.text)
    normalize = normalize_results or normalize_search_results
    return await normalize(parser.results, max_results)


async def search_tavily(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    api_key: str | None = None,
    normalize_results: SearchNormalizer | None = None,
) -> SearchResults:
    selected_api_key = (api_key or settings.tavily_api_key).strip()
    response = await client.post(
        "https://api.tavily.com/search",
        json={
            "query": query,
            "search_depth": settings.tavily_search_depth.strip() or "basic",
            "max_results": max_results,
            "include_answer": False,
        },
        headers={"Authorization": f"Bearer {selected_api_key}"},
    )
    response.raise_for_status()
    payload = response.json()
    raw_results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(raw_results, list):
        return []

    results: SearchResults = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "snippet": str(
                    item.get("content") or item.get("snippet") or ""
                ).strip(),
            }
        )
    normalize = normalize_results or normalize_search_results
    return await normalize(results, max_results)


async def search_sogou(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    normalize_results: SearchNormalizer | None = None,
) -> SearchResults:
    response = await client.get(
        "https://www.sogou.com/web",
        params={"query": query},
    )
    response.raise_for_status()

    parser = SogouResultParser()
    parser.feed(response.text)
    normalize = normalize_results or normalize_search_results
    return await normalize(parser.results, max_results)


async def search_yahoo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    normalize_results: SearchNormalizer | None = None,
) -> SearchResults:
    response = await client.get(
        "https://search.yahoo.com/search",
        params={"p": query},
    )
    response.raise_for_status()

    parser = YahooResultParser()
    parser.feed(response.text)
    normalize = normalize_results or normalize_search_results
    return await normalize(parser.results, max_results)


async def normalize_search_results(
    results: SearchResults,
    max_results: int,
    *,
    is_blocked_search_result_url: Callable[[str], bool] | None = None,
) -> SearchResults:
    blocked_url = (
        is_blocked_search_result_url or globals()["is_blocked_search_result_url"]
    )
    normalized: SearchResults = []
    seen_urls: set[str] = set()
    for result in results:
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        if not title or not url or url in seen_urls or blocked_url(url):
            continue
        seen_urls.add(url)
        normalized.append(
            {
                "title": truncate_text(title, MAX_SEARCH_TITLE_CHARS),
                "url": url,
                "snippet": truncate_text(
                    (result.get("snippet") or "").strip(),
                    MAX_SEARCH_SNIPPET_CHARS,
                ),
            }
        )
        if len(normalized) >= max_results:
            break
    return normalized
