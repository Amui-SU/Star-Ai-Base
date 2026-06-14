import json

import pytest
from fastapi import HTTPException

from app.models import ChatRequest, KnowledgeBaseChatRequest
from app.routers.chat import (
    LLMProviderConfigRequest,
    THINKING_DELTA_MARKER,
    _build_thinking_completion_options,
    _complete_llm_answer,
    _encode_thinking_delta,
    _get_provider_thinking_config,
    _get_provider_thinking_template,
    _parse_thinking_config,
    _stream_llm_events,
    save_llm_provider_config,
)


def test_chat_request_models_no_longer_expose_request_mode_switches():
    assert "smart_search" not in ChatRequest.model_fields
    assert "smart_search" not in KnowledgeBaseChatRequest.model_fields
    assert "deep_think" not in ChatRequest.model_fields
    assert "deep_think" not in KnowledgeBaseChatRequest.model_fields


def test_deepseek_thinking_uses_native_request_json():
    options = _build_thinking_completion_options(
        {
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
        }
    )

    assert options == {
        "extra_body": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        }
    }


def test_dashscope_thinking_uses_enable_thinking_request_json():
    options = _build_thinking_completion_options(
        {"thinking_config": {"enable_thinking": True}}
    )

    assert options == {"extra_body": {"enable_thinking": True}}


def test_disabled_thinking_adds_no_upstream_fields():
    assert _build_thinking_completion_options({"thinking_config": {}}) == {}


def test_provider_standard_templates_are_request_body_fragments():
    assert _get_provider_thinking_template("deepseek") == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert _get_provider_thinking_template("dashscope") == {"enable_thinking": True}
    assert _get_provider_thinking_template("kimi") == {}


def test_custom_thinking_config_requires_json_object():
    assert _parse_thinking_config('{"thinking":{"type":"enabled"}}') == {
        "thinking": {"type": "enabled"}
    }
    with pytest.raises(HTTPException, match="JSON 对象"):
        _parse_thinking_config('["not", "an", "object"]')
    with pytest.raises(HTTPException, match="JSON 格式"):
        _parse_thinking_config("{bad json")


def test_provider_thinking_config_reads_persisted_json(monkeypatch):
    monkeypatch.setattr(
        "app.routers.chat.settings.deepseek_thinking_config",
        json.dumps({"thinking": {"type": "enabled"}}),
    )

    assert _get_provider_thinking_config("deepseek") == {
        "thinking": {"type": "enabled"}
    }


@pytest.mark.asyncio
async def test_save_provider_standard_thinking_verifies_then_persists(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda provider=None: {
            "provider": "deepseek",
            "provider_label": "DeepSeek",
            "api_key": "saved-key",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr(
        "app.routers.chat._verify_provider_configuration",
        lambda config: captured.setdefault("verified_config", config) and 123,
    )
    monkeypatch.setattr(
        "app.routers.chat._write_env_values",
        lambda updates: captured.setdefault("updates", updates),
    )

    result = await save_llm_provider_config(
        LLMProviderConfigRequest(
            provider="deepseek",
            thinking_mode="standard",
        )
    )

    assert captured["verified_config"]["thinking_config"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert json.loads(captured["updates"]["DEEPSEEK_THINKING_CONFIG"]) == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert result["verified"] is True
    assert result["latency_ms"] == 123


def test_thinking_delta_is_json_encoded_for_mixed_text_stream():
    encoded = _encode_thinking_delta("分析\n下一步")

    assert encoded == f'{THINKING_DELTA_MARKER}"分析\\n下一步"\n'


def test_stream_llm_events_forwards_native_reasoning_and_answer(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            reasoning_delta = type(
                "Delta",
                (),
                {"reasoning_content": "先分析", "content": None},
            )()
            answer_delta = type(
                "Delta",
                (),
                {"reasoning_content": None, "content": "最终答案"},
            )()
            return [
                type(
                    "Chunk",
                    (),
                    {"choices": [type("Choice", (), {"delta": reasoning_delta})()]},
                )(),
                type(
                    "Chunk",
                    (),
                    {"choices": [type("Choice", (), {"delta": answer_delta})()]},
                )(),
            ]

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    events = list(_stream_llm_events([{"role": "user", "content": "问题"}]))

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert events == [("thinking", "先分析"), ("answer", "最终答案")]


def test_complete_llm_answer_returns_native_reasoning(monkeypatch):
    captured = {}
    message = type(
        "Message",
        (),
        {"content": "最终答案", "reasoning_content": "先分析"},
    )()

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": message})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking = _complete_llm_answer(
        [{"role": "user", "content": "问题"}],
    )

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert answer == "最终答案"
    assert thinking == "先分析"
