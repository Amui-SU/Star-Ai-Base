"""Router dependency assembly for legacy chat endpoints."""

from typing import Any

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_runtime import answer_legacy_chat, stream_legacy_chat


async def answer_legacy_chat_from_router(
    request: ChatRequest,
    db: Any,
    *,
    router_module: Any,
    warning_logger,
) -> ChatResponse:
    return await answer_legacy_chat(
        request,
        db,
        resolve_llm_config=router_module._resolve_llm_config,
        prepare_messages=router_module._prepare_messages,
        enforce_markdown_output=router_module._enforce_markdown_output,
        apply_mode_instructions=router_module._apply_mode_instructions,
        get_llm_client=router_module._get_llm_client,
        build_completion_request_options=(
            router_module._build_completion_request_options
        ),
        extract_thinking_and_answer=router_module._extract_thinking_and_answer,
        is_llm_connection_error=router_module._is_llm_connection_error,
        build_llm_unavailable_answer=router_module._build_llm_unavailable_answer,
        warning_logger=warning_logger,
    )


async def stream_legacy_chat_from_router(
    request: ChatRequest,
    db: Any,
    *,
    router_module: Any,
    warning_logger,
):
    return await stream_legacy_chat(
        request,
        db,
        resolve_llm_config=router_module._resolve_llm_config,
        prepare_messages=router_module._prepare_messages,
        enforce_markdown_output=router_module._enforce_markdown_output,
        apply_mode_instructions=router_module._apply_mode_instructions,
        stream_llm_events=router_module._stream_llm_events,
        encode_thinking_delta=router_module._encode_thinking_delta,
        is_llm_connection_error=router_module._is_llm_connection_error,
        build_llm_unavailable_answer=router_module._build_llm_unavailable_answer,
        warning_logger=warning_logger,
    )
