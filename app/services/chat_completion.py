"""LLM completion, streaming, and tool-loop helpers for chat flows."""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Optional

from fastapi import HTTPException
from openai import APIConnectionError, APITimeoutError

from app.services.api_account_requests import build_account_request_options
from app.services.llm_tool_calls import (
    LLMToolRunResult,
    append_no_more_tool_calls_instruction,
    append_tool_call_results,
    contains_dsml_tool_call_text,
    extract_dsml_text_tool_calls,
    extract_thinking_and_answer,
)

DEFAULT_THINKING_DELTA_MARKER = "[[THINKING_DELTA]]"


async def create_chat_completion_async(client: Any, **kwargs):
    return await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))


def is_llm_connection_error(err: Exception) -> bool:
    """判断是否为上游模型连接/超时问题"""
    if isinstance(err, (APIConnectionError, APITimeoutError)):
        return True
    text = str(err).lower()
    return "connection error" in text or "timed out" in text or "timeout" in text


def build_llm_unavailable_answer() -> str:
    """模型不可用时的用户可读兜底回答"""
    return (
        "当前 AI 模型服务连接不稳定，暂时无法生成回答。\n\n"
        "你可以先尝试：\n"
        "1. 稍后重试提问；\n"
        "2. 检查后端网络与模型服务配置（API Key / Base URL）；\n"
        "3. 先在左侧完成收藏夹入库，稍后再问。"
    )


def build_completion_request_options(
    llm_config: dict,
    *,
    system_body: dict | None = None,
) -> dict:
    return build_account_request_options(llm_config, system_body=system_body)


def build_thinking_completion_options(llm_config: dict) -> dict:
    """把已保存的请求体 JSON 注入 OpenAI 兼容客户端。"""
    return build_completion_request_options(llm_config)


def verify_provider_configuration(
    llm_config: dict,
    *,
    get_llm_client: Callable[[dict], Any],
) -> int:
    start = time.perf_counter()
    client = get_llm_client(llm_config)
    try:
        client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "请只回复 OK"}],
            stream=False,
            **build_completion_request_options(
                llm_config, system_body={"max_tokens": 16}
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="模型配置验证失败",
        ) from exc
    return int((time.perf_counter() - start) * 1000)


def encode_thinking_delta(
    content: str, marker: str = DEFAULT_THINKING_DELTA_MARKER
) -> str:
    return f"{marker}{json.dumps(content, ensure_ascii=False)}\n"


def stream_llm_events(
    messages: list[dict],
    llm_config: Optional[dict[str, str]] = None,
    *,
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
) -> Iterable[tuple[str, str]]:
    """Yield native thinking and answer deltas from the configured model."""
    cfg = llm_config or resolve_llm_config()
    client = get_llm_client(cfg)
    stream = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        stream=True,
        **build_completion_request_options(cfg, system_body={"temperature": 0.5}),
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning_piece = getattr(delta, "reasoning_content", None)
        if reasoning_piece:
            yield "thinking", reasoning_piece
        if delta and delta.content:
            yield "answer", delta.content


def complete_llm_answer(
    messages: list[dict],
    llm_config: Optional[dict[str, str]] = None,
    *,
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
) -> tuple[str, str]:
    cfg = llm_config or resolve_llm_config()
    client = get_llm_client(cfg)
    response = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        **build_completion_request_options(cfg, system_body={"temperature": 0.5}),
    )
    message = response.choices[0].message
    thinking, answer = extract_thinking_and_answer(
        message.content or "",
        getattr(message, "reasoning_content", None),
    )
    return answer, thinking


async def complete_llm_answer_with_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    max_tool_calls: int = 2,
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
) -> tuple[str, str, list[dict]]:
    tool_run = await prepare_llm_messages_with_tools(
        messages,
        tools=tools,
        tool_handlers=tool_handlers,
        max_tool_calls=max_tool_calls,
        resolve_llm_config=resolve_llm_config,
        get_llm_client=get_llm_client,
    )
    if tool_run.answer is not None:
        return tool_run.answer, tool_run.thinking, tool_run.messages

    llm_config = resolve_llm_config()
    client = get_llm_client(llm_config)
    response = await create_chat_completion_async(
        client,
        model=llm_config["model"],
        messages=append_no_more_tool_calls_instruction(tool_run.messages),
        **build_completion_request_options(
            llm_config, system_body={"temperature": 0.5}
        ),
    )
    message = response.choices[0].message
    thinking, answer = extract_thinking_and_answer(
        message.content or "",
        getattr(message, "reasoning_content", None),
    )
    if contains_dsml_tool_call_text(answer):
        response = await create_chat_completion_async(
            client,
            model=llm_config["model"],
            messages=append_no_more_tool_calls_instruction(
                [
                    *tool_run.messages,
                    {
                        "role": "assistant",
                        "content": ("我刚刚仍输出了工具调用文本，这不是最终答案。"),
                    },
                ]
            ),
            **build_completion_request_options(
                llm_config, system_body={"temperature": 0.5}
            ),
        )
        message = response.choices[0].message
        thinking, answer = extract_thinking_and_answer(
            message.content or "",
            getattr(message, "reasoning_content", None),
        )
    return answer, thinking, tool_run.messages


async def prepare_llm_messages_with_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    max_tool_calls: int = 2,
    after_tool_messages: Optional[Callable[[list[dict]], list[dict]]] = None,
    llm_config: Optional[dict[str, str]] = None,
    resolve_llm_config: Callable[[], dict],
    get_llm_client: Callable[[dict], Any],
) -> LLMToolRunResult:
    cfg = llm_config or resolve_llm_config()
    client = get_llm_client(cfg)
    working_messages = [*messages]
    executed_tool_calls = 0

    while executed_tool_calls < max_tool_calls:
        # Keep tool planning fast; final answer generation still uses thinking config.
        response = await create_chat_completion_async(
            client,
            model=cfg["model"],
            messages=working_messages,
            tools=tools,
            tool_choice="auto",
            **build_completion_request_options(
                {**cfg, "thinking_config": {}},
                system_body={"temperature": 0.5},
            ),
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            content, text_tool_calls = extract_dsml_text_tool_calls(
                message.content or ""
            )
            if text_tool_calls:
                message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": text_tool_calls,
                }
                tool_calls = text_tool_calls
            else:
                thinking, answer = extract_thinking_and_answer(
                    message.content or "",
                    getattr(message, "reasoning_content", None),
                )
                return LLMToolRunResult(
                    messages=working_messages,
                    answer=answer,
                    thinking=thinking,
                )

        if not tool_calls:
            thinking, answer = extract_thinking_and_answer(
                message.content or "",
                getattr(message, "reasoning_content", None),
            )
            return LLMToolRunResult(
                messages=working_messages,
                answer=answer,
                thinking=thinking,
            )

        working_messages, executed_this_round = await append_tool_call_results(
            working_messages,
            message,
            tool_calls,
            tool_handlers=tool_handlers,
            remaining_tool_calls=max_tool_calls - executed_tool_calls,
        )
        if after_tool_messages is not None:
            working_messages = after_tool_messages(working_messages)
        executed_tool_calls += executed_this_round

    return LLMToolRunResult(messages=working_messages)
