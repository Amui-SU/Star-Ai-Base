"""LLM client factory shared by chat runtimes."""

from collections.abc import Callable, Mapping
from typing import Any, Optional

from anthropic import Anthropic
from fastapi import HTTPException
from openai import OpenAI

from app.services.anthropic_chat_adapter import AnthropicChatClientFacade
from app.services.chat_provider_catalog import _resolve_llm_config


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
    client = factory(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=30.0,
        max_retries=2,
    )
    if cfg.get("protocol") == "anthropic_messages":
        return anthropic_facade_factory(client)
    return client
