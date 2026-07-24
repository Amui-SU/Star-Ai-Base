from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.chat_completion import (
    build_llm_unavailable_answer,
    build_completion_request_options,
    build_thinking_completion_options,
    complete_llm_answer,
    encode_thinking_delta,
    is_llm_connection_error,
    verify_provider_configuration,
)


def test_build_thinking_completion_options_uses_extra_body():
    assert build_thinking_completion_options(
        {"thinking_config": {"reasoning_effort": "high"}}
    ) == {"extra_body": {"reasoning_effort": "high"}}
    assert build_thinking_completion_options({"thinking_config": {}}) == {}
    assert build_completion_request_options(
        {"advanced_config": {"headers": {"X-Route": "chat"}}}
    ) == {"extra_headers": {"X-Route": "chat"}}


def test_encode_thinking_delta_json_encodes_content():
    assert (
        encode_thinking_delta("分析\n下一步") == '[[THINKING_DELTA]]"分析\\n下一步"\n'
    )


def test_is_llm_connection_error_matches_timeout_text():
    assert is_llm_connection_error(RuntimeError("request timed out"))
    assert is_llm_connection_error(RuntimeError("connection error from upstream"))
    assert not is_llm_connection_error(RuntimeError("bad request"))


def test_build_llm_unavailable_answer_is_user_readable():
    answer = build_llm_unavailable_answer()

    assert "AI 模型服务连接不稳定" in answer
    assert "稍后重试" in answer


def test_verify_provider_configuration_uses_injected_client():
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    latency_ms = verify_provider_configuration(
        {
            "model": "fake-model",
            "thinking_config": {"enable_thinking": True},
            "advanced_config": {
                "user_agent": "Verifier/1.0",
                "body": {"top_p": 0.7},
            },
        },
        get_llm_client=lambda config: client,
    )

    assert captured["model"] == "fake-model"
    assert captured["messages"] == [{"role": "user", "content": "请只回复 OK"}]
    assert captured["extra_headers"] == {"User-Agent": "Verifier/1.0"}
    assert captured["extra_body"] == {
        "max_tokens": 16,
        "top_p": 0.7,
        "enable_thinking": True,
    }
    assert isinstance(latency_ms, int)


def test_verify_provider_configuration_wraps_failures():
    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    with pytest.raises(HTTPException, match="模型配置验证失败"):
        verify_provider_configuration(
            {"model": "fake-model", "thinking_config": {}},
            get_llm_client=lambda config: client,
        )


def test_complete_llm_answer_uses_injected_runtime_dependencies():
    captured = {}
    message = SimpleNamespace(content="最终答案", reasoning_content="先分析")

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    answer, thinking = complete_llm_answer(
        [{"role": "user", "content": "问题"}],
        resolve_llm_config=lambda: {
            "model": "fake-model",
            "thinking_config": {"reasoning_effort": "high"},
        },
        get_llm_client=lambda config: client,
    )

    assert answer == "最终答案"
    assert thinking == "先分析"
    assert captured["model"] == "fake-model"
    assert captured["extra_body"] == {
        "temperature": 0.5,
        "reasoning_effort": "high",
    }
