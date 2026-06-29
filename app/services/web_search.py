import asyncio

import httpx
from loguru import logger

from app.config import settings
from app.services.web_page_fetcher import (
    compact_text as _compact_text,
    fetch_web_page as _fetch_web_page,
    truncate_text as _truncate_text,
)
from app.services.web_search_parsers import (
    DuckDuckGoResultParser,
    SogouResultParser,
    YahooResultParser,
)
from app.services.web_search_safety import (
    is_blocked_address as _is_blocked_address,
    is_blocked_search_result_url as _is_blocked_search_result_url,
    is_blocked_url as _is_blocked_url_impl,
    is_proxy_fake_ip_address as _is_proxy_fake_ip_address,
    resolve_hostname as _resolve_hostname_impl,
    resolve_public_hostname as _resolve_public_hostname_impl,
    resolved_host as _resolved_host,
)

MAX_SEARCH_QUERY_CHARS = 240
MAX_SEARCH_TITLE_CHARS = 180
MAX_SEARCH_SNIPPET_CHARS = 600
SEARCH_PROVIDERS = ("tavily", "duckduckgo", "yahoo", "sogou")


async def _cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    pending_tasks = [task for task in tasks if not task.done()]
    if not pending_tasks:
        return
    for task in pending_tasks:
        task.cancel()
    await asyncio.gather(*pending_tasks, return_exceptions=True)


def _sort_provider_diagnostics(diagnostics: list[dict] | None) -> None:
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


async def _resolve_hostname(hostname: str, port: int = 80) -> list:
    return await _resolve_hostname_impl(hostname, port)


async def _resolve_public_hostname(hostname: str) -> list[str]:
    return await _resolve_public_hostname_impl(hostname)


async def _is_blocked_url(url: str) -> bool:
    return await _is_blocked_url_impl(
        url,
        resolve_hostname_fn=_resolve_hostname,
        resolve_public_hostname_fn=_resolve_public_hostname,
    )


async def search_web(
    query: str,
    *,
    max_results: int = 3,
    diagnostics: list[dict] | None = None,
    provider: str | None = None,
    tavily_api_key: str | None = None,
) -> list[dict[str, str]]:
    """Return lightweight web search snippets for LLM grounding."""
    term = _truncate_text(query.strip(), MAX_SEARCH_QUERY_CHARS)
    if not term:
        return []

    provider_override = provider is not None
    selected_provider = (provider or settings.web_search_provider).strip().lower()
    if selected_provider not in {"auto", "tavily", "html"}:
        selected_provider = settings.web_search_provider.strip().lower() or "html"
    selected_tavily_key = (tavily_api_key or settings.tavily_api_key).strip()
    timeout = httpx.Timeout(8.0, connect=4.0)
    proxy = settings.http_proxy or None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        proxy=proxy,
        headers=headers,
        trust_env=False,
    ) as client:
        if selected_provider in {"auto", "tavily"}:
            if not selected_tavily_key:
                _append_missing_tavily_key_diagnostic(diagnostics)
                if (
                    provider_override and selected_provider == "tavily"
                ) or not settings.web_search_fallback_html:
                    _sort_provider_diagnostics(diagnostics)
                    return []
            else:
                tavily_results = await _try_search_provider(
                    "tavily",
                    _search_tavily,
                    client,
                    term,
                    max_results=max_results,
                    diagnostics=diagnostics,
                    api_key=selected_tavily_key,
                )
                if (
                    tavily_results
                    or (provider_override and selected_provider == "tavily")
                    or not settings.web_search_fallback_html
                ):
                    _sort_provider_diagnostics(diagnostics)
                    return tavily_results

        return await _search_html_providers(
            client,
            term,
            max_results=max_results,
            diagnostics=diagnostics,
        )


def _append_missing_tavily_key_diagnostic(diagnostics: list[dict] | None) -> None:
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


async def _search_html_providers(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: list[dict] | None = None,
) -> list[dict[str, str]]:
    combined: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    provider_tasks = [
        asyncio.create_task(
            _try_search_provider(
                provider,
                searcher,
                client,
                query,
                max_results=max_results,
                diagnostics=diagnostics,
            )
        )
        for provider, searcher in (
            ("duckduckgo", _search_duckduckgo),
            ("yahoo", _search_yahoo),
            ("sogou", _search_sogou),
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
                    await _cancel_pending_tasks(provider_tasks)
                    _sort_provider_diagnostics(diagnostics)
                    return combined
    finally:
        await _cancel_pending_tasks(provider_tasks)
    _sort_provider_diagnostics(diagnostics)
    return combined


async def _try_search_provider(
    provider: str,
    searcher,
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: list[dict] | None = None,
    **search_kwargs,
) -> list[dict[str, str]]:
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
                    "message": _truncate_text(str(exc), 240) or "搜索源请求失败",
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


async def _search_duckduckgo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
    )
    response.raise_for_status()

    parser = DuckDuckGoResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _search_tavily(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    api_key: str | None = None,
) -> list[dict[str, str]]:
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

    results: list[dict[str, str]] = []
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
    return await _normalize_search_results(
        results,
        max_results=max_results,
    )


async def _search_sogou(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.get(
        "https://www.sogou.com/web",
        params={"query": query},
    )
    response.raise_for_status()

    parser = SogouResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _search_yahoo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.get(
        "https://search.yahoo.com/search",
        params={"p": query},
    )
    response.raise_for_status()

    parser = YahooResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _normalize_search_results(
    results: list[dict[str, str]],
    *,
    max_results: int,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for result in results:
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        if (
            not title
            or not url
            or url in seen_urls
            or _is_blocked_search_result_url(url)
        ):
            continue
        seen_urls.add(url)
        normalized.append(
            {
                "title": _truncate_text(title, MAX_SEARCH_TITLE_CHARS),
                "url": url,
                "snippet": _truncate_text(
                    (result.get("snippet") or "").strip(),
                    MAX_SEARCH_SNIPPET_CHARS,
                ),
            }
        )
        if len(normalized) >= max_results:
            break
    return normalized


async def fetch_web_page(
    url: str,
    *,
    max_chars: int = 4000,
    max_bytes: int = 256_000,
) -> dict[str, str]:
    return await _fetch_web_page(
        url,
        max_chars=max_chars,
        max_bytes=max_bytes,
        is_blocked_url_fn=_is_blocked_url,
    )
