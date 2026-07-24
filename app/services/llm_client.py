"""LLM client factory shared by chat runtimes."""

from collections.abc import Callable, Mapping
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from anthropic import Anthropic
from fastapi import HTTPException
from openai import OpenAI

from app.services.anthropic_chat_adapter import AnthropicChatClientFacade
from app.services.chat_provider_catalog import _resolve_llm_config


def normalize_anthropic_base_url(base_url: str) -> str:
    """Remove a trailing v1 segment because the Anthropic SDK adds it."""
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if path.rsplit("/", 1)[-1] != "v1":
        return base_url
    normalized_path = path[: -len("/v1")]
    return urlunsplit(parsed._replace(path=normalized_path))


def get_llm_client(
    llm_config: Optional[Mapping[str, Any]] = None,
    *,
    resolve_llm_config: Callable[[], Mapping[str, Any]] = _resolve_llm_config,
    client_factory: Callable[..., Any] = OpenAI,
    anthropic_client_factory: Callable[..., Any] = Anthropic,
    anthropic_facade_factory: Callable[[Any], Any] = AnthropicChatClientFacade,
) -> Any:
    cfg = llm_config or resolve_llm_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 LLM API Key")
    if cfg.get("provider") == "tavily" or (
        "provider" in cfg and cfg.get("provider") is None
    ):
        raise HTTPException(status_code=400, detail="Provider is not an LLM")
    factory = (
        anthropic_client_factory
        if cfg.get("protocol") == "anthropic_messages"
        else client_factory
    )
    base_url = cfg["base_url"]
    if cfg.get("protocol") == "anthropic_messages":
        base_url = normalize_anthropic_base_url(base_url)
    client = factory(
        api_key=cfg["api_key"],
        base_url=base_url,
        timeout=30.0,
        max_retries=2,
    )
    if cfg.get("protocol") == "anthropic_messages":
        return anthropic_facade_factory(client)
    return client
