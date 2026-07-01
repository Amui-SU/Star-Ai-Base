import pytest
from fastapi import HTTPException

from app.services.chat_health import llm_health_response


class FakeCredential:
    def __init__(self, llm_config):
        self._llm_config = llm_config

    def to_llm_config(self):
        return self._llm_config


class FakeCompletionClient:
    def __init__(self, calls, error=None):
        self.chat = type(
            "FakeChat",
            (),
            {"completions": FakeCompletions(calls, error)},
        )()


class FakeCompletions:
    def __init__(self, calls, error=None):
        self._calls = calls
        self._error = error

    def create(self, **kwargs):
        self._calls.append(kwargs)
        if self._error is not None:
            raise self._error


@pytest.mark.asyncio
async def test_llm_health_response_uses_resolved_credentials_for_ping():
    llm_config = {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key": "personal-key",
        "base_url": "https://api.deepseek.com",
    }
    calls = []

    async def resolve_llm_credentials(db, current_user, *, global_config_resolver):
        assert db == "db"
        assert current_user == "user"
        assert global_config_resolver()["provider"] == "fallback"
        return FakeCredential(llm_config)

    result = await llm_health_response(
        "db",
        "user",
        resolve_llm_credentials=resolve_llm_credentials,
        global_config_resolver=lambda: {"provider": "fallback", "model": "fallback"},
        get_llm_client=lambda config: FakeCompletionClient(calls),
        warning_logger=lambda message: None,
        perf_counter=iter([1.0, 1.123]).__next__,
    )

    assert result == {
        "status": "ok",
        "message": "模型服务可用",
        "latency_ms": 123,
        "model": "deepseek-chat",
        "provider": "deepseek",
    }
    assert calls == [
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
    ]


@pytest.mark.asyncio
async def test_llm_health_response_returns_down_without_probe_when_credentials_missing():
    async def resolve_llm_credentials(db, current_user, *, global_config_resolver):
        raise HTTPException(
            status_code=400,
            detail={"message": "需要配置个人 AI 服务密钥"},
        )

    def fail_if_called(_config):
        raise AssertionError("health check should not probe without credentials")

    result = await llm_health_response(
        "db",
        "user",
        resolve_llm_credentials=resolve_llm_credentials,
        global_config_resolver=lambda: {"provider": "official", "model": "fallback"},
        get_llm_client=fail_if_called,
        warning_logger=lambda message: None,
    )

    assert result == {
        "status": "down",
        "message": "需要配置个人 AI 服务密钥",
        "latency_ms": None,
        "model": "fallback",
        "provider": "official",
    }


@pytest.mark.asyncio
async def test_llm_health_response_reports_probe_failure_with_latency_and_model():
    llm_config = {
        "provider": "dashscope",
        "model": "qwen-plus",
        "api_key": "saved-key",
        "base_url": "https://dashscope.aliyuncs.com",
    }
    warnings = []

    async def resolve_llm_credentials(db, current_user, *, global_config_resolver):
        return FakeCredential(llm_config)

    result = await llm_health_response(
        "db",
        "user",
        resolve_llm_credentials=resolve_llm_credentials,
        global_config_resolver=lambda: {"provider": "fallback", "model": "fallback"},
        get_llm_client=lambda config: FakeCompletionClient(
            [],
            RuntimeError("network timeout"),
        ),
        warning_logger=warnings.append,
        perf_counter=iter([2.0, 2.25]).__next__,
    )

    assert result == {
        "status": "down",
        "message": "network timeout",
        "latency_ms": 250,
        "model": "qwen-plus",
        "provider": "dashscope",
    }
    assert warnings == ["LLM 健康检查失败: network timeout"]
