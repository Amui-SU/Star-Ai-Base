"""LLM runtime adapters used by knowledge-base chat routes."""

import json
from collections.abc import Awaitable, Callable
from typing import Any


WEB_SEARCH_PROGRESS_MARKER = "[[WEB_SEARCH_PROGRESS]]"


def build_stream_llm_events_adapter(
    *,
    stream_llm_events: Callable[..., Any],
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
):
    def adapter(messages: list[dict], llm_config: dict | None = None):
        return stream_llm_events(
            messages,
            llm_config,
            resolve_llm_config=resolve_llm_config,
            get_llm_client=get_llm_client,
        )

    return adapter


def build_complete_llm_answer_adapter(
    *,
    complete_llm_answer: Callable[..., tuple[str, str]],
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
):
    def adapter(
        messages: list[dict],
        llm_config: dict | None = None,
    ) -> tuple[str, str]:
        return complete_llm_answer(
            messages,
            llm_config,
            resolve_llm_config=resolve_llm_config,
            get_llm_client=get_llm_client,
        )

    return adapter


def build_prepare_llm_messages_with_tools_adapter(
    *,
    prepare_llm_messages_with_tools: Callable[..., Awaitable[Any]],
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
):
    async def adapter(
        messages: list[dict],
        *,
        tools: list[dict],
        tool_handlers: dict,
        max_tool_calls: int = 2,
        after_tool_messages=None,
        llm_config: dict | None = None,
    ):
        return await prepare_llm_messages_with_tools(
            messages,
            tools=tools,
            tool_handlers=tool_handlers,
            max_tool_calls=max_tool_calls,
            after_tool_messages=after_tool_messages,
            llm_config=llm_config,
            resolve_llm_config=resolve_llm_config,
            get_llm_client=get_llm_client,
        )

    return adapter


def encode_web_search_progress(content: str) -> str:
    return f"{WEB_SEARCH_PROGRESS_MARKER}{json.dumps(content, ensure_ascii=False)}\n"
