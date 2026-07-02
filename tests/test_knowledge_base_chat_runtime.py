from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_answer_runtime_uses_router_module_dependencies(monkeypatch):
    from app.services import knowledge_base_chat_runtime as runtime

    captured = {}

    async def fake_answer(db, **kwargs):
        captured["db"] = db
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(runtime, "answer_knowledge_base_chat", fake_answer)
    module = SimpleNamespace(
        _load_scoped_chat_documents=object(),
        _answer_from_documents=object(),
        resolve_user_llm_credentials=object(),
        _resolve_llm_config=object(),
        _resolve_web_search_api_key=object(),
        _build_knowledge_base_messages=object(),
        _complete_knowledge_base_answer=object(),
        _supports_keyword_argument=object(),
        record_usage_event=object(),
        _source_from_document=object(),
        _source_from_web_result=object(),
        _web_search_failed_status_from_exception=object(),
    )
    warning_logger = object()

    result = await runtime.answer_knowledge_base_chat_from_router(
        "db",
        payload="payload",
        knowledge_base="knowledge_base",
        user="user",
        workspace="workspace",
        router_module=module,
        warning_logger=warning_logger,
    )

    assert result == "response"
    assert captured["db"] == "db"
    assert captured["payload"] == "payload"
    assert captured["knowledge_base"] == "knowledge_base"
    assert captured["user"] == "user"
    assert captured["workspace"] == "workspace"
    assert captured["load_documents"] is module._load_scoped_chat_documents
    assert captured["answer_from_documents"] is module._answer_from_documents
    assert captured["resolve_llm_credentials"] is module.resolve_user_llm_credentials
    assert captured["global_config_resolver"] is module._resolve_llm_config
    assert captured["resolve_web_search_api_key"] is module._resolve_web_search_api_key
    assert captured["build_messages"] is module._build_knowledge_base_messages
    assert captured["complete_answer"] is module._complete_knowledge_base_answer
    assert captured["supports_keyword_argument"] is module._supports_keyword_argument
    assert captured["record_usage"] is module.record_usage_event
    assert captured["source_from_document"] is module._source_from_document
    assert captured["source_from_web_result"] is module._source_from_web_result
    assert (
        captured["web_search_failed_status_from_exception"]
        is module._web_search_failed_status_from_exception
    )
    assert captured["warning_logger"] is warning_logger


@pytest.mark.asyncio
async def test_stream_runtime_uses_router_module_dependencies(monkeypatch):
    from app.services import knowledge_base_chat_runtime as runtime

    captured = {}

    async def fake_stream(db, **kwargs):
        captured["db"] = db
        captured.update(kwargs)
        return "stream"

    monkeypatch.setattr(runtime, "stream_knowledge_base_chat", fake_stream)
    module = SimpleNamespace(
        _load_scoped_chat_documents=object(),
        _answer_from_documents=object(),
        resolve_user_llm_credentials=object(),
        _resolve_llm_config=object(),
        _resolve_web_search_api_key=object(),
        _build_knowledge_base_messages=object(),
        _prepare_knowledge_base_web_search_with_heartbeats=object(),
        _append_no_more_tool_calls_instruction=object(),
        _stream_llm_events=object(),
        _supports_keyword_argument=object(),
        _encode_web_search_progress=object(),
        _encode_thinking_delta=object(),
        _source_from_document=object(),
        _source_from_web_result=object(),
        _web_search_failed_status_from_exception=object(),
        record_usage_event=object(),
    )
    warning_logger = object()

    result = await runtime.stream_knowledge_base_chat_from_router(
        "db",
        payload="payload",
        knowledge_base="knowledge_base",
        user="user",
        workspace="workspace",
        router_module=module,
        warning_logger=warning_logger,
    )

    assert result == "stream"
    assert captured["db"] == "db"
    assert captured["payload"] == "payload"
    assert captured["knowledge_base"] == "knowledge_base"
    assert captured["user"] == "user"
    assert captured["workspace"] == "workspace"
    assert captured["load_documents"] is module._load_scoped_chat_documents
    assert captured["answer_from_documents"] is module._answer_from_documents
    assert captured["resolve_llm_credentials"] is module.resolve_user_llm_credentials
    assert captured["global_config_resolver"] is module._resolve_llm_config
    assert captured["resolve_web_search_api_key"] is module._resolve_web_search_api_key
    assert captured["build_messages"] is module._build_knowledge_base_messages
    assert (
        captured["prepare_web_search_with_heartbeats"]
        is module._prepare_knowledge_base_web_search_with_heartbeats
    )
    assert (
        captured["append_no_more_tool_calls_instruction"]
        is module._append_no_more_tool_calls_instruction
    )
    assert captured["stream_llm_events"] is module._stream_llm_events
    assert captured["supports_keyword_argument"] is module._supports_keyword_argument
    assert captured["encode_web_search_progress"] is module._encode_web_search_progress
    assert captured["encode_thinking_delta"] is module._encode_thinking_delta
    assert captured["source_from_document"] is module._source_from_document
    assert captured["source_from_web_result"] is module._source_from_web_result
    assert (
        captured["web_search_failed_status_from_exception"]
        is module._web_search_failed_status_from_exception
    )
    assert captured["record_usage"] is module.record_usage_event
    assert captured["warning_logger"] is warning_logger
