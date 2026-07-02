import httpx
from functools import partial

from app.config import settings
from app.services.web_page_fetcher import (
    compact_text as _compact_text,
    fetch_web_page as _fetch_web_page,
    truncate_text as _truncate_text,
)
from app.services.web_search_providers import (
    SEARCH_PROVIDERS,
    append_missing_tavily_key_diagnostic as _append_missing_tavily_key_diagnostic,
    cancel_pending_tasks as _cancel_pending_tasks,
    normalize_search_results,
    search_duckduckgo,
    search_html_providers,
    search_sogou,
    search_tavily,
    search_yahoo,
    sort_provider_diagnostics as _sort_provider_diagnostics,
    try_search_provider,
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


_normalize_search_results = partial(
    normalize_search_results,
    is_blocked_search_result_url=_is_blocked_search_result_url,
)
_search_duckduckgo = partial(
    search_duckduckgo,
    normalize_results=_normalize_search_results,
)
_search_tavily = partial(
    search_tavily,
    normalize_results=_normalize_search_results,
)
_search_sogou = partial(
    search_sogou,
    normalize_results=_normalize_search_results,
)
_search_yahoo = partial(
    search_yahoo,
    normalize_results=_normalize_search_results,
)
_search_html_providers = partial(
    search_html_providers,
    duckduckgo_searcher=_search_duckduckgo,
    yahoo_searcher=_search_yahoo,
    sogou_searcher=_search_sogou,
)
_try_search_provider = try_search_provider


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
