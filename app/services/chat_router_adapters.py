"""Compatibility adapter assembly for legacy chat router modules."""

from typing import Any

from app.services.chat_llm_runtime import (
    build_complete_llm_answer_adapter,
    build_complete_llm_answer_with_tools_adapter,
    build_prepare_llm_messages_with_tools_adapter,
    build_stream_llm_events_adapter,
)


def build_chat_router_adapters(
    module: Any,
    *,
    stream_llm_events,
    complete_llm_answer,
    complete_llm_answer_with_tools,
    prepare_llm_messages_with_tools,
    encode_thinking_delta,
    thinking_delta_marker: str,
) -> dict[str, Any]:
    """Build legacy monkeypatch-compatible LLM helpers for chat routes."""

    return {
        "_encode_thinking_delta": (
            lambda content: encode_thinking_delta(content, thinking_delta_marker)
        ),
        "_stream_llm_events": build_stream_llm_events_adapter(
            stream_llm_events=stream_llm_events,
            resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
            get_llm_client=lambda config: getattr(module, "_get_llm_client")(config),
        ),
        "_complete_llm_answer": build_complete_llm_answer_adapter(
            complete_llm_answer=complete_llm_answer,
            resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
            get_llm_client=lambda config: getattr(module, "_get_llm_client")(config),
        ),
        "_complete_llm_answer_with_tools": build_complete_llm_answer_with_tools_adapter(
            complete_llm_answer_with_tools=complete_llm_answer_with_tools,
            resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
            get_llm_client=lambda config: getattr(module, "_get_llm_client")(config),
        ),
        "_prepare_llm_messages_with_tools": (
            build_prepare_llm_messages_with_tools_adapter(
                prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
                resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
                get_llm_client=lambda config: getattr(module, "_get_llm_client")(
                    config
                ),
            )
        ),
    }
