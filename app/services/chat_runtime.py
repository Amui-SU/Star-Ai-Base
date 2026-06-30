"""Runtime orchestration for legacy chat routes."""

import json
from collections.abc import Callable, Iterable
from typing import Any

from app.schemas.chat import ChatRequest, ChatResponse


async def answer_legacy_chat(
    request: ChatRequest,
    db: Any,
    *,
    resolve_llm_config: Callable[[], dict[str, Any]],
    prepare_messages: Callable[..., Any],
    enforce_markdown_output: Callable[[list[dict]], list[dict]],
    apply_mode_instructions: Callable[[list[dict], bool], list[dict]],
    get_llm_client: Callable[[dict[str, Any]], Any],
    build_thinking_completion_options: Callable[[dict[str, Any]], dict[str, Any]],
    extract_thinking_and_answer: Callable[[str, Any], tuple[str, str]],
    is_llm_connection_error: Callable[[Exception], bool],
    build_llm_unavailable_answer: Callable[[], str],
    warning_logger: Callable[[str], None],
) -> ChatResponse:
    """Answer a non-streaming legacy chat request."""
    llm_config = resolve_llm_config()
    messages, sources, _ = await prepare_messages(request, db)
    messages = enforce_markdown_output(messages)
    messages = apply_mode_instructions(
        messages,
        bool(llm_config["thinking_config"]),
    )
    client = get_llm_client(llm_config)
    try:
        response = client.chat.completions.create(
            model=llm_config["model"],
            messages=messages,
            temperature=0.5,
            **build_thinking_completion_options(llm_config),
        )
        message = response.choices[0].message
        raw_answer = message.content or ""
        reasoning = getattr(message, "reasoning_content", None)
        thinking, answer = extract_thinking_and_answer(raw_answer, reasoning)
        return ChatResponse(
            answer=answer, sources=sources[:5], thinking=thinking or None
        )
    except Exception as exc:
        if is_llm_connection_error(exc):
            warning_logger(f"模型连接异常，使用降级回答: {exc}")
            return ChatResponse(
                answer=build_llm_unavailable_answer(),
                sources=sources[:5],
                thinking=None,
            )
        raise


async def stream_legacy_chat(
    request: ChatRequest,
    db: Any,
    *,
    resolve_llm_config: Callable[[], dict[str, Any]],
    prepare_messages: Callable[..., Any],
    enforce_markdown_output: Callable[[list[dict]], list[dict]],
    apply_mode_instructions: Callable[[list[dict], bool], list[dict]],
    stream_llm_events: Callable[[list[dict]], Iterable[tuple[str, str]]],
    encode_thinking_delta: Callable[[str], str],
    is_llm_connection_error: Callable[[Exception], bool],
    build_llm_unavailable_answer: Callable[[], str],
    warning_logger: Callable[[str], None],
) -> Iterable[str]:
    """Prepare a streaming legacy chat response body."""
    llm_config = resolve_llm_config()
    messages, sources, _ = await prepare_messages(request, db)
    messages = enforce_markdown_output(messages)
    messages = apply_mode_instructions(
        messages,
        bool(llm_config["thinking_config"]),
    )

    def generate() -> Iterable[str]:
        thinking_parts: list[str] = []
        try:
            for event_type, content in stream_llm_events(messages):
                if event_type == "thinking":
                    thinking_parts.append(content)
                    yield encode_thinking_delta(content)
                else:
                    yield content
        except Exception as exc:
            if is_llm_connection_error(exc):
                warning_logger(f"流式模型连接异常，使用降级回答: {exc}")
                yield build_llm_unavailable_answer()
            else:
                raise
        if thinking_parts:
            yield (
                "\n[[THINKING_JSON]]"
                f"{json.dumps(''.join(thinking_parts), ensure_ascii=False)}"
            )
        yield f"\n[[SOURCES_JSON]]{json.dumps(sources, ensure_ascii=False)}"

    return generate()
