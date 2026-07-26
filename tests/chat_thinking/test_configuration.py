import json

import pytest
from fastapi import HTTPException

from app.services.chat_completion import (
    build_thinking_completion_options as _build_thinking_completion_options,
)
from app.services.chat_config import _get_provider_thinking_config
from app.routers.chat import (
    LLMProviderConfigRequest,
    WebSearchConfigRequest,
    _get_provider_thinking_template,
    _parse_thinking_config,
    get_web_search_config,
    save_llm_provider_config,
    save_web_search_config,
)


@pytest.mark.asyncio
async def test_web_search_config_hides_tavily_key(monkeypatch):
    monkeypatch.setattr("app.routers.chat.settings.web_search_provider", "tavily")
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "tvly-secret")
    monkeypatch.setattr("app.routers.chat.settings.web_search_fallback_html", True)
    monkeypatch.setattr("app.routers.chat.settings.tavily_search_depth", "advanced")

    result = await get_web_search_config()

    assert result == {
        "provider": "tavily",
        "tavily_configured": True,
        "fallback_html": True,
        "tavily_search_depth": "advanced",
    }
    assert "tavily_api_key" not in result
    assert "api_key" not in result


@pytest.mark.asyncio
async def test_save_web_search_config_persists_tavily_key_without_echoing_it(
    monkeypatch,
):
    captured = {}
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "")
    monkeypatch.setattr(
        "app.routers.chat._write_env_values",
        lambda updates: captured.setdefault("updates", updates),
    )

    result = await save_web_search_config(
        WebSearchConfigRequest(
            provider="tavily",
            tavily_api_key="tvly-test",
            fallback_html=False,
            tavily_search_depth="advanced",
        )
    )

    assert captured["updates"] == {
        "WEB_SEARCH_PROVIDER": "tavily",
        "WEB_SEARCH_FALLBACK_HTML": "false",
        "TAVILY_SEARCH_DEPTH": "advanced",
        "TAVILY_API_KEY": "tvly-test",
    }
    assert result["provider"] == "tavily"
    assert result["tavily_configured"] is True
    assert "tavily_api_key" not in result
    assert "api_key" not in result


@pytest.mark.asyncio
async def test_save_web_search_config_requires_key_for_tavily(monkeypatch):
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "")

    with pytest.raises(HTTPException) as exc:
        await save_web_search_config(WebSearchConfigRequest(provider="tavily"))

    assert exc.value.status_code == 400


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
