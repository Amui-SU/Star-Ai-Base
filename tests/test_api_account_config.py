from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.services.api_account_config import (
    SUPPORTED_API_PROVIDERS,
    default_advanced_config,
    normalize_advanced_config,
    normalize_provider,
    provider_defaults,
    provider_preset,
    resolve_account_model,
)

EXPECTED_PROVIDER_DEFAULTS = {
    "dashscope": (
        "阿里云 DashScope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-max",
    ),
    "deepseek": ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    "agnes": ("Agnes", "https://apihub.agnes-ai.com/v1", "agnes-2.0-flash"),
    "claude": (
        "Claude",
        "https://api.anthropic.com/v1",
        "claude-haiku-4-5",
    ),
    "kimi": ("Moonshot Kimi", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    "siliconflow": (
        "SiliconFlow",
        "https://api.siliconflow.cn/v1",
        "Qwen/Qwen2.5-7B-Instruct",
    ),
    "zhipu": ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "tavily": ("Tavily", "https://api.tavily.com", "tavily-search"),
}


def test_provider_presets_expose_protocol_auth_kind_and_website():
    claude = provider_preset(" CLAUDE ")
    assert claude.protocol == "anthropic_messages"
    assert claude.auth_scheme == "x_api_key"
    assert claude.kind == "llm"
    assert claude.website_url == "https://www.anthropic.com/"

    tavily = provider_preset("tavily")
    assert tavily.protocol is None
    assert tavily.auth_scheme is None
    assert tavily.kind == "search"
    assert tavily.website_url == "https://tavily.com/"

    for provider in SUPPORTED_API_PROVIDERS - {"claude", "tavily"}:
        preset = provider_preset(provider)
        assert preset.protocol == "openai_compatible"
        assert preset.auth_scheme == "bearer"
        assert preset.kind == "llm"
        assert preset.website_url.startswith("https://")


def test_provider_defaults_and_normalization_remain_compatible():
    assert SUPPORTED_API_PROVIDERS == set(EXPECTED_PROVIDER_DEFAULTS)
    assert normalize_provider(" DeepSeek ") == "deepseek"

    for provider, (label, base_url, model) in EXPECTED_PROVIDER_DEFAULTS.items():
        defaults = provider_defaults(provider)
        assert defaults.label == label
        assert defaults.base_url == base_url
        assert defaults.model == model

    with pytest.raises(HTTPException) as exc_info:
        normalize_provider("unknown-provider")
    assert exc_info.value.status_code == 400


def test_default_advanced_config_uses_v1_shape():
    assert default_advanced_config("gpt-test") == {
        "version": 1,
        "model_mapping": {},
        "fallback_model": "gpt-test",
        "user_agent": "",
        "headers": {},
        "body": {},
    }


def test_normalize_advanced_config_fills_defaults_and_preserves_unknown_fields():
    source = {
        "model_mapping": {"chat": "provider-chat"},
        "headers": {"X-Feature": "enabled"},
        "body": {"temperature": 0.2},
        "extension": {"nested": ["value"]},
    }
    original = deepcopy(source)

    normalized = normalize_advanced_config(source, model="legacy-default")

    assert normalized == {
        "version": 1,
        "model_mapping": {"chat": "provider-chat"},
        "fallback_model": "legacy-default",
        "user_agent": "",
        "headers": {"X-Feature": "enabled"},
        "body": {"temperature": 0.2},
        "extension": {"nested": ["value"]},
    }
    assert source == original
    assert normalized is not source
    assert normalized["extension"] is not source["extension"]


def test_normalize_advanced_config_treats_non_dict_as_empty():
    assert normalize_advanced_config(["ignored"], model="fallback") == (
        default_advanced_config("fallback")
    )


@pytest.mark.parametrize(
    ("value", "field"),
    [
        ({"version": 2}, "version"),
        ({"version": "1"}, "version"),
        ({"model_mapping": []}, "model_mapping"),
        ({"model_mapping": {"": "valid"}}, "model_mapping"),
        ({"model_mapping": {"alias": ""}}, "model_mapping.alias"),
        ({"fallback_model": 42}, "fallback_model"),
        ({"user_agent": 42}, "user_agent"),
        ({"user_agent": "client\r\ninjected"}, "user_agent"),
        ({"headers": []}, "headers"),
        ({"headers": {"X-Test": 1}}, "headers.X-Test"),
        ({"body": []}, "body"),
    ],
)
def test_normalize_advanced_config_rejects_invalid_types_and_values(value, field):
    with pytest.raises(HTTPException) as exc_info:
        normalize_advanced_config(value)

    assert exc_info.value.status_code == 400
    assert field in str(exc_info.value.detail)


@pytest.mark.parametrize(
    "header",
    [
        "aUtHoRiZaTiOn",
        "X-API-Key",
        "api-key",
        "x-goog-api-key",
        "User-Agent",
        "Host",
        "Content-Length",
        "Transfer-Encoding",
        "Connection",
        "Forwarded",
        "X-Forwarded-For",
        "Traceparent",
        "X-Request-ID",
        "X-Cloud-Trace-Context",
        "X-Datadog-Trace-Id",
        "X-Trace-Id",
    ],
)
def test_normalize_advanced_config_rejects_protected_headers_without_value_leak(
    header,
):
    secret = "must-not-be-reflected"
    with pytest.raises(HTTPException) as exc_info:
        normalize_advanced_config({"headers": {header: secret}})

    detail = str(exc_info.value.detail)
    assert exc_info.value.status_code == 400
    assert header in detail
    assert secret not in detail


def test_normalize_advanced_config_allows_business_x_headers():
    assert normalize_advanced_config({"headers": {"X-Workspace": "research"}})[
        "headers"
    ] == {"X-Workspace": "research"}


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "messages",
        "input",
        "prompt",
        "tools",
        "tool_choice",
        "stream",
        "response_format",
    ],
)
def test_normalize_advanced_config_rejects_protected_body_fields(field):
    with pytest.raises(HTTPException) as exc_info:
        normalize_advanced_config({"body": {field: "must-not-be-reflected"}})

    detail = str(exc_info.value.detail)
    assert exc_info.value.status_code == 400
    assert f"body.{field}" in detail
    assert "must-not-be-reflected" not in detail


def test_resolve_account_model_uses_alias_before_fallback():
    config = normalize_advanced_config(
        {
            "model_mapping": {"chat": "provider-chat"},
            "fallback_model": "provider-fallback",
        }
    )

    assert resolve_account_model("chat", config, "legacy") == "provider-chat"
    assert resolve_account_model("unmapped", config, "legacy") == "provider-fallback"


def test_resolve_account_model_does_not_remap_fallback():
    config = normalize_advanced_config(
        {
            "model_mapping": {"fallback-alias": "remapped"},
            "fallback_model": "fallback-alias",
        }
    )

    assert resolve_account_model("", config, "legacy") == "fallback-alias"


def test_resolve_account_model_uses_legacy_then_fails_when_all_models_are_empty():
    config = default_advanced_config()
    assert resolve_account_model("", config, "legacy-model") == "legacy-model"

    with pytest.raises(HTTPException) as exc_info:
        resolve_account_model("", config, "")
    assert exc_info.value.status_code == 400
    assert "model" in str(exc_info.value.detail).lower()
