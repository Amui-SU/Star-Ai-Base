from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_answer_route_runtime_uses_router_module_dependencies(monkeypatch):
    from app.services import chat_route_runtime as runtime

    captured = {}

    async def fake_answer(request, db, **kwargs):
        captured["request"] = request
        captured["db"] = db
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(runtime, "answer_legacy_chat", fake_answer)
    module = SimpleNamespace(
        _resolve_llm_config=object(),
        _prepare_messages=object(),
        _enforce_markdown_output=object(),
        _apply_mode_instructions=object(),
        _get_llm_client=object(),
        _build_completion_request_options=object(),
        _extract_thinking_and_answer=object(),
        _is_llm_connection_error=object(),
        _build_llm_unavailable_answer=object(),
    )
    warning_logger = object()

    result = await runtime.answer_legacy_chat_from_router(
        "request",
        "db",
        router_module=module,
        warning_logger=warning_logger,
    )

    assert result == "response"
    assert captured["request"] == "request"
    assert captured["db"] == "db"
    assert captured["resolve_llm_config"] is module._resolve_llm_config
    assert captured["prepare_messages"] is module._prepare_messages
    assert captured["enforce_markdown_output"] is module._enforce_markdown_output
    assert captured["apply_mode_instructions"] is module._apply_mode_instructions
    assert captured["get_llm_client"] is module._get_llm_client
    assert (
        captured["build_completion_request_options"]
        is module._build_completion_request_options
    )
    assert (
        captured["extract_thinking_and_answer"] is module._extract_thinking_and_answer
    )
    assert captured["is_llm_connection_error"] is module._is_llm_connection_error
    assert (
        captured["build_llm_unavailable_answer"] is module._build_llm_unavailable_answer
    )
    assert captured["warning_logger"] is warning_logger


@pytest.mark.asyncio
async def test_stream_route_runtime_uses_router_module_dependencies(monkeypatch):
    from app.services import chat_route_runtime as runtime

    captured = {}

    async def fake_stream(request, db, **kwargs):
        captured["request"] = request
        captured["db"] = db
        captured.update(kwargs)
        return "stream"

    monkeypatch.setattr(runtime, "stream_legacy_chat", fake_stream)
    module = SimpleNamespace(
        _resolve_llm_config=object(),
        _prepare_messages=object(),
        _enforce_markdown_output=object(),
        _apply_mode_instructions=object(),
        _stream_llm_events=object(),
        _encode_thinking_delta=object(),
        _is_llm_connection_error=object(),
        _build_llm_unavailable_answer=object(),
    )
    warning_logger = object()

    result = await runtime.stream_legacy_chat_from_router(
        "request",
        "db",
        router_module=module,
        warning_logger=warning_logger,
    )

    assert result == "stream"
    assert captured["request"] == "request"
    assert captured["db"] == "db"
    assert captured["resolve_llm_config"] is module._resolve_llm_config
    assert captured["prepare_messages"] is module._prepare_messages
    assert captured["enforce_markdown_output"] is module._enforce_markdown_output
    assert captured["apply_mode_instructions"] is module._apply_mode_instructions
    assert captured["stream_llm_events"] is module._stream_llm_events
    assert captured["encode_thinking_delta"] is module._encode_thinking_delta
    assert captured["is_llm_connection_error"] is module._is_llm_connection_error
    assert (
        captured["build_llm_unavailable_answer"] is module._build_llm_unavailable_answer
    )
    assert captured["warning_logger"] is warning_logger
