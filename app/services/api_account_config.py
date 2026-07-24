from copy import deepcopy
from dataclasses import dataclass
from typing import Literal
import unicodedata

from fastapi import HTTPException


@dataclass(frozen=True)
class ProviderPreset:
    label: str
    base_url: str
    model: str
    protocol: Literal["openai_compatible", "anthropic_messages"] | None
    auth_scheme: Literal["bearer", "x_api_key"] | None
    website_url: str
    kind: Literal["llm", "search"]


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "dashscope": ProviderPreset(
        label="阿里云 DashScope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-max",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://www.aliyun.com/product/bailian",
        kind="llm",
    ),
    "deepseek": ProviderPreset(
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://www.deepseek.com/",
        kind="llm",
    ),
    "openai": ProviderPreset(
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://openai.com/",
        kind="llm",
    ),
    "agnes": ProviderPreset(
        label="Agnes",
        base_url="https://apihub.agnes-ai.com/v1",
        model="agnes-2.0-flash",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://agnes-ai.com/",
        kind="llm",
    ),
    "claude": ProviderPreset(
        label="Claude",
        base_url="https://api.anthropic.com/v1",
        model="claude-haiku-4-5",
        protocol="anthropic_messages",
        auth_scheme="x_api_key",
        website_url="https://www.anthropic.com/",
        kind="llm",
    ),
    "kimi": ProviderPreset(
        label="Moonshot Kimi",
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://www.moonshot.cn/",
        kind="llm",
    ),
    "siliconflow": ProviderPreset(
        label="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://siliconflow.cn/",
        kind="llm",
    ),
    "zhipu": ProviderPreset(
        label="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-flash",
        protocol="openai_compatible",
        auth_scheme="bearer",
        website_url="https://www.bigmodel.cn/",
        kind="llm",
    ),
    "tavily": ProviderPreset(
        label="Tavily",
        base_url="https://api.tavily.com",
        model="tavily-search",
        protocol=None,
        auth_scheme=None,
        website_url="https://tavily.com/",
        kind="search",
    ),
}

SUPPORTED_API_PROVIDERS = set(PROVIDER_PRESETS)

_PROTECTED_HEADER_NAMES = {
    "authorization",
    "baggage",
    "cdn-loop",
    "connection",
    "content-length",
    "forwarded",
    "host",
    "proxy-authorization",
    "traceparent",
    "tracestate",
    "transfer-encoding",
    "user-agent",
    "via",
    "x-amzn-trace-id",
    "x-client-ip",
    "x-correlation-id",
    "x-real-ip",
    "x-request-id",
}
_PROTECTED_HEADER_PREFIXES = (
    "cf-connecting-",
    "x-b3-",
    "x-envoy-",
    "x-forwarded-",
    "x-original-",
    "x-proxy-",
)
_PROTECTED_BODY_FIELDS = {
    "input",
    "messages",
    "model",
    "prompt",
    "response_format",
    "stream",
    "tool_choice",
    "tools",
}


def _bad_config(field: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=f"Invalid advanced_config field: {field}",
    )


def normalize_provider(value: str) -> str:
    provider = (value or "").strip().lower()
    if provider not in SUPPORTED_API_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported API provider")
    return provider


def provider_preset(provider: str) -> ProviderPreset:
    return PROVIDER_PRESETS[normalize_provider(provider)]


def provider_defaults(provider: str) -> ProviderPreset:
    return provider_preset(provider)


def default_advanced_config(model: str = "") -> dict:
    return {
        "version": 1,
        "model_mapping": {},
        "fallback_model": model,
        "user_agent": "",
        "headers": {},
        "body": {},
    }


def _contains_control_character(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _normalize_model_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise _bad_config("model_mapping")
    for alias, mapped_model in value.items():
        if not isinstance(alias, str) or not alias.strip():
            raise _bad_config("model_mapping")
        if not isinstance(mapped_model, str) or not mapped_model.strip():
            field = (
                f"model_mapping.{alias}" if isinstance(alias, str) else "model_mapping"
            )
            raise _bad_config(field)
    return value


def _is_protected_header(header: str) -> bool:
    normalized = header.strip().lower().replace("_", "-")
    compact = "".join(character for character in normalized if character.isalnum())
    return (
        normalized in _PROTECTED_HEADER_NAMES
        or any(normalized.startswith(prefix) for prefix in _PROTECTED_HEADER_PREFIXES)
        or "apikey" in compact
        or compact.endswith("subscriptionkey")
    )


def _normalize_headers(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise _bad_config("headers")
    for header, header_value in value.items():
        if not isinstance(header, str) or not header.strip():
            raise _bad_config("headers")
        field = f"headers.{header}"
        if not isinstance(header_value, str):
            raise _bad_config(field)
        if _contains_control_character(header) or _is_protected_header(header):
            raise _bad_config(field)
        if _contains_control_character(header_value):
            raise _bad_config(field)
    return value


def _normalize_body(value: object) -> dict:
    if not isinstance(value, dict):
        raise _bad_config("body")
    for field in value:
        if not isinstance(field, str):
            raise _bad_config("body")
        if field.lower() in _PROTECTED_BODY_FIELDS:
            raise _bad_config(f"body.{field}")
    return value


def normalize_advanced_config(value: object, model: str = "") -> dict:
    source = value if isinstance(value, dict) else {}
    normalized = default_advanced_config(model)
    normalized.update(deepcopy(source))

    if type(normalized.get("version")) is not int or normalized["version"] != 1:
        raise _bad_config("version")
    normalized["model_mapping"] = _normalize_model_mapping(
        normalized.get("model_mapping")
    )

    fallback_model = normalized.get("fallback_model")
    if not isinstance(fallback_model, str):
        raise _bad_config("fallback_model")

    user_agent = normalized.get("user_agent")
    if not isinstance(user_agent, str) or _contains_control_character(user_agent):
        raise _bad_config("user_agent")

    normalized["headers"] = _normalize_headers(normalized.get("headers"))
    normalized["body"] = _normalize_body(normalized.get("body"))
    return normalized


def resolve_account_model(
    requested_model: str,
    advanced_config: object,
    legacy_model: str,
) -> str:
    normalized = normalize_advanced_config(advanced_config)
    requested = requested_model.strip() if isinstance(requested_model, str) else ""
    mapped_model = normalized["model_mapping"].get(requested)
    if mapped_model:
        return mapped_model

    fallback_model = normalized["fallback_model"]
    if fallback_model.strip():
        return fallback_model

    legacy = legacy_model if isinstance(legacy_model, str) else ""
    if legacy.strip():
        return legacy
    raise HTTPException(status_code=400, detail="No API account model configured")
