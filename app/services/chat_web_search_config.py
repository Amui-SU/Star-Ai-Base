"""Web-search configuration helpers for chat."""

from typing import Callable, Dict, Optional

from fastapi import HTTPException

from app.config import settings
from app.services.chat_config_env import _write_env_values

SUPPORTED_WEB_SEARCH_PROVIDERS = {"auto", "tavily", "html"}
SUPPORTED_TAVILY_SEARCH_DEPTHS = {"basic", "advanced"}


def _normalize_web_search_provider(provider: Optional[str]) -> str:
    normalized = (provider or "auto").strip().lower()
    if normalized not in SUPPORTED_WEB_SEARCH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported web search provider")
    return normalized


def _normalize_tavily_search_depth(depth: Optional[str]) -> str:
    normalized = (depth or "basic").strip().lower()
    if normalized not in SUPPORTED_TAVILY_SEARCH_DEPTHS:
        raise HTTPException(status_code=400, detail="Unsupported Tavily search depth")
    return normalized


def _web_search_config_response(
    provider: str,
    *,
    tavily_configured: bool | None = None,
) -> dict:
    return {
        "provider": provider,
        "tavily_configured": (
            bool(settings.tavily_api_key.strip())
            if tavily_configured is None
            else tavily_configured
        ),
        "fallback_html": bool(settings.web_search_fallback_html),
        "tavily_search_depth": _normalize_tavily_search_depth(
            settings.tavily_search_depth
        ),
    }


def save_global_web_search_config(
    *,
    provider: str,
    tavily_api_key: Optional[str] = None,
    fallback_html: bool = True,
    tavily_search_depth: str = "basic",
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
) -> dict:
    """Persist global web-search settings without echoing saved secrets."""
    normalized_provider = _normalize_web_search_provider(provider)
    normalized_depth = _normalize_tavily_search_depth(tavily_search_depth)
    tavily_key = (tavily_api_key or "").strip()
    existing_tavily_key = settings.tavily_api_key.strip()
    if normalized_provider == "tavily" and not (tavily_key or existing_tavily_key):
        raise HTTPException(status_code=400, detail="Tavily API Key cannot be empty")

    updates = {
        "WEB_SEARCH_PROVIDER": normalized_provider,
        "WEB_SEARCH_FALLBACK_HTML": "true" if fallback_html else "false",
        "TAVILY_SEARCH_DEPTH": normalized_depth,
    }
    if tavily_key:
        updates["TAVILY_API_KEY"] = tavily_key

    env_writer(updates)
    settings.web_search_provider = normalized_provider
    settings.web_search_fallback_html = fallback_html
    settings.tavily_search_depth = normalized_depth
    if tavily_key:
        settings.tavily_api_key = tavily_key

    return _web_search_config_response(normalized_provider)
