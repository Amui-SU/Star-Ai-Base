from types import SimpleNamespace

import pytest

from app.schemas.chat import ChatRequest
from app.services.chat_runtime import answer_legacy_chat, stream_legacy_chat


async def _prepare_messages(_request, _db):
    return [{"role": "user", "content": "问题"}], [{"title": "来源"}], "问题"


def _resolve_llm_config():
    return {"model": "fake-model", "thinking_config": {"enabled": True}}


def _identity_messages(messages):
    return messages


def _apply_mode_instructions(messages, _thinking_enabled):
    return [*messages, {"role": "system", "content": "mode"}]


def _completion_options(_config, *, system_body=None):
    return {
        "extra_headers": {"X-Runtime": "legacy"},
        "extra_body": {**(system_body or {}), "enabled": True},
    }


def _extract_thinking_and_answer(_content, reasoning):
    return reasoning or "", "最终答案"


@pytest.mark.asyncio
async def test_answer_legacy_chat_builds_chat_response_with_runtime_dependencies():
    captured = {}
    message = SimpleNamespace(content="raw answer", reasoning_content="先想")

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    response = await answer_legacy_chat(
        ChatRequest(question="问题"),
        db=object(),
        resolve_llm_config=_resolve_llm_config,
        prepare_messages=_prepare_messages,
        enforce_markdown_output=_identity_messages,
        apply_mode_instructions=_apply_mode_instructions,
        get_llm_client=lambda _config: client,
        build_completion_request_options=_completion_options,
        extract_thinking_and_answer=_extract_thinking_and_answer,
        is_llm_connection_error=lambda _exc: False,
        build_llm_unavailable_answer=lambda: "fallback",
        warning_logger=lambda _message: None,
    )

    assert response.answer == "最终答案"
    assert response.thinking == "先想"
    assert response.sources == [{"title": "来源"}]
    assert captured["model"] == "fake-model"
    assert captured["messages"][-1] == {"role": "system", "content": "mode"}
    assert captured["extra_headers"] == {"X-Runtime": "legacy"}
    assert captured["extra_body"] == {"temperature": 0.5, "enabled": True}


@pytest.mark.asyncio
async def test_answer_legacy_chat_falls_back_on_connection_error():
    class FakeCompletions:
        def create(self, **_kwargs):
            raise RuntimeError("timeout")

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    warnings = []

    response = await answer_legacy_chat(
        ChatRequest(question="问题"),
        db=object(),
        resolve_llm_config=_resolve_llm_config,
        prepare_messages=_prepare_messages,
        enforce_markdown_output=_identity_messages,
        apply_mode_instructions=_apply_mode_instructions,
        get_llm_client=lambda _config: client,
        build_completion_request_options=_completion_options,
        extract_thinking_and_answer=_extract_thinking_and_answer,
        is_llm_connection_error=lambda _exc: True,
        build_llm_unavailable_answer=lambda: "模型暂不可用",
        warning_logger=warnings.append,
    )

    assert response.answer == "模型暂不可用"
    assert response.thinking is None
    assert warnings


@pytest.mark.asyncio
async def test_stream_legacy_chat_emits_thinking_and_sources_trailers():
    stream = await stream_legacy_chat(
        ChatRequest(question="问题"),
        db=object(),
        resolve_llm_config=_resolve_llm_config,
        prepare_messages=_prepare_messages,
        enforce_markdown_output=_identity_messages,
        apply_mode_instructions=_apply_mode_instructions,
        stream_llm_events=lambda _messages: [
            ("thinking", "先想"),
            ("answer", "答"),
        ],
        encode_thinking_delta=lambda content: f"THINK:{content}\n",
        is_llm_connection_error=lambda _exc: False,
        build_llm_unavailable_answer=lambda: "fallback",
        warning_logger=lambda _message: None,
    )

    body = "".join(stream)

    assert body.startswith("THINK:先想\n答")
    assert '[[THINKING_JSON]]"先想"' in body
    assert '[[SOURCES_JSON]][{"title": "来源"}]' in body


@pytest.mark.asyncio
async def test_stream_legacy_chat_falls_back_on_connection_error():
    warnings = []

    def raise_timeout(_messages):
        raise RuntimeError("timeout")
        yield ("answer", "unreachable")

    stream = await stream_legacy_chat(
        ChatRequest(question="问题"),
        db=object(),
        resolve_llm_config=_resolve_llm_config,
        prepare_messages=_prepare_messages,
        enforce_markdown_output=_identity_messages,
        apply_mode_instructions=_apply_mode_instructions,
        stream_llm_events=raise_timeout,
        encode_thinking_delta=lambda content: content,
        is_llm_connection_error=lambda _exc: True,
        build_llm_unavailable_answer=lambda: "模型暂不可用",
        warning_logger=warnings.append,
    )

    body = "".join(stream)

    assert "模型暂不可用" in body
    assert '[[SOURCES_JSON]][{"title": "来源"}]' in body
    assert warnings
