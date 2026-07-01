"""LLM client factory shared by chat runtimes."""

from collections.abc import Callable, Mapping
from typing import Any, Optional

from fastapi import HTTPException
from openai import OpenAI

from app.services.chat_provider_catalog import _resolve_llm_config


def get_llm_client(
    llm_config: Optional[Mapping[str, Any]] = None,
    *,
    resolve_llm_config: Callable[[], Mapping[str, Any]] = _resolve_llm_config,
    client_factory: Callable[..., Any] = OpenAI,
) -> Any:
    cfg = llm_config or resolve_llm_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 LLM API Key")
    return client_factory(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=30.0,
        max_retries=2,
    )
