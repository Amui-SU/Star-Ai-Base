import importlib.util
import json

import pytest
from fastapi import HTTPException


def test_provider_catalog_resolves_config_and_thinking(monkeypatch):
    assert importlib.util.find_spec("app.services.chat_provider_catalog") is not None
    from app.config import settings
    from app.services.chat_provider_catalog import PROVIDER_ENV_FIELDS
    from app.services.chat_provider_catalog import _current_default_llm_provider
    from app.services.chat_provider_catalog import _get_provider_thinking_config
    from app.services.chat_provider_catalog import _get_provider_thinking_template
    from app.services.chat_provider_catalog import _normalize_provider
    from app.services.chat_provider_catalog import _resolve_llm_config

    monkeypatch.setattr(settings, "llm_provider", "unknown")
    monkeypatch.setattr(settings, "deepseek_api_key", "deepseek-key")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://api.deepseek.test")
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-chat")
    monkeypatch.setattr(
        settings,
        "deepseek_thinking_config",
        json.dumps({"thinking": {"type": "enabled"}}),
    )

    assert PROVIDER_ENV_FIELDS["deepseek"]["api_key"] == "DEEPSEEK_API_KEY"
    assert _current_default_llm_provider() == "dashscope"
    assert _normalize_provider(" DEEPSEEK ") == "deepseek"
    assert _get_provider_thinking_template("deepseek") == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert _get_provider_thinking_config("deepseek") == {
        "thinking": {"type": "enabled"}
    }

    assert _resolve_llm_config("deepseek") == {
        "provider": "deepseek",
        "provider_label": "DeepSeek",
        "api_key": "deepseek-key",
        "base_url": "https://api.deepseek.test",
        "model": "deepseek-chat",
        "thinking_config": {"thinking": {"type": "enabled"}},
    }


def test_provider_catalog_supports_agnes_and_claude(monkeypatch):
    assert importlib.util.find_spec("app.services.chat_provider_catalog") is not None
    from app.config import settings
    from app.services.chat_provider_catalog import PROVIDER_ENV_FIELDS
    from app.services.chat_provider_catalog import _get_provider_thinking_template
    from app.services.chat_provider_catalog import _resolve_llm_config

    monkeypatch.setattr(settings, "agnes_api_key", "agnes-key")
    monkeypatch.setattr(settings, "agnes_base_url", "https://agnes.example/v1")
    monkeypatch.setattr(settings, "agnes_model", "agnes-2.0-flash")
    monkeypatch.setattr(settings, "claude_api_key", "claude-key")
    monkeypatch.setattr(settings, "claude_base_url", "https://claude.example/v1")
    monkeypatch.setattr(settings, "claude_model", "claude-sonnet-test")
    monkeypatch.setattr(
        settings,
        "claude_thinking_config",
        '{"thinking":{"type":"enabled"}}',
    )

    assert PROVIDER_ENV_FIELDS["agnes"] == {
        "api_key": "AGNES_API_KEY",
        "base_url": "AGNES_BASE_URL",
        "model": "AGNES_MODEL",
        "thinking_config": "AGNES_THINKING_CONFIG",
    }
    assert PROVIDER_ENV_FIELDS["claude"] == {
        "api_key": "CLAUDE_API_KEY",
        "base_url": "CLAUDE_BASE_URL",
        "model": "CLAUDE_MODEL",
        "thinking_config": "CLAUDE_THINKING_CONFIG",
    }

    assert _resolve_llm_config("agnes") == {
        "provider": "agnes",
        "provider_label": "Agnes",
        "api_key": "agnes-key",
        "base_url": "https://agnes.example/v1",
        "model": "agnes-2.0-flash",
        "thinking_config": {},
    }
    assert _resolve_llm_config("claude") == {
        "provider": "claude",
        "provider_label": "Claude",
        "api_key": "claude-key",
        "base_url": "https://claude.example/v1",
        "model": "claude-sonnet-test",
        "thinking_config": {"thinking": {"type": "enabled"}},
    }
    assert _get_provider_thinking_template("claude") == {
        "thinking": {"type": "enabled", "budget_tokens": 2000}
    }


def test_provider_catalog_rejects_invalid_provider_and_thinking_json():
    assert importlib.util.find_spec("app.services.chat_provider_catalog") is not None
    from app.services.chat_provider_catalog import _normalize_provider
    from app.services.chat_provider_catalog import _parse_thinking_config

    with pytest.raises(HTTPException) as provider_exc:
        _normalize_provider("unsupported")
    assert provider_exc.value.status_code == 400

    with pytest.raises(HTTPException) as json_exc:
        _parse_thinking_config("{bad json")
    assert json_exc.value.status_code == 400

    with pytest.raises(HTTPException) as object_exc:
        _parse_thinking_config('["not", "object"]')
    assert object_exc.value.status_code == 400
