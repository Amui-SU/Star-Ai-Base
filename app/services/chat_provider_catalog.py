"""LLM provider catalog and thinking-configuration helpers."""

import json
from typing import Dict, Optional

from fastapi import HTTPException

from app.config import settings

PROVIDER_META = {
    "dashscope": {
        "label": "阿里云 DashScope",
        "api_key": lambda: settings.openai_api_key,
        "base_url": lambda: settings.openai_base_url,
        "model": lambda: settings.llm_model,
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_key": lambda: settings.deepseek_api_key,
        "base_url": lambda: settings.deepseek_base_url,
        "model": lambda: settings.deepseek_model,
    },
    "openai": {
        "label": "OpenAI",
        "api_key": lambda: settings.openai_native_api_key,
        "base_url": lambda: settings.openai_native_base_url,
        "model": lambda: settings.openai_native_model,
    },
    "agnes": {
        "label": "Agnes",
        "api_key": lambda: settings.agnes_api_key,
        "base_url": lambda: settings.agnes_base_url,
        "model": lambda: settings.agnes_model,
    },
    "claude": {
        "label": "Claude",
        "api_key": lambda: settings.claude_api_key,
        "base_url": lambda: settings.claude_base_url,
        "model": lambda: settings.claude_model,
    },
    "kimi": {
        "label": "Moonshot Kimi",
        "api_key": lambda: settings.kimi_api_key,
        "base_url": lambda: settings.kimi_base_url,
        "model": lambda: settings.kimi_model,
    },
    "siliconflow": {
        "label": "SiliconFlow",
        "api_key": lambda: settings.siliconflow_api_key,
        "base_url": lambda: settings.siliconflow_base_url,
        "model": lambda: settings.siliconflow_model,
    },
    "zhipu": {
        "label": "智谱 GLM",
        "api_key": lambda: settings.zhipu_api_key,
        "base_url": lambda: settings.zhipu_base_url,
        "model": lambda: settings.zhipu_model,
    },
}
SUPPORTED_LLM_PROVIDERS = set(PROVIDER_META.keys())


PROVIDER_ENV_FIELDS = {
    "dashscope": {
        "api_key": "DASHSCOPE_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "model": "LLM_MODEL",
        "thinking_config": "DASHSCOPE_THINKING_CONFIG",
    },
    "deepseek": {
        "api_key": "DEEPSEEK_API_KEY",
        "base_url": "DEEPSEEK_BASE_URL",
        "model": "DEEPSEEK_MODEL",
        "thinking_config": "DEEPSEEK_THINKING_CONFIG",
    },
    "openai": {
        "api_key": "OPENAI_NATIVE_API_KEY",
        "base_url": "OPENAI_NATIVE_BASE_URL",
        "model": "OPENAI_NATIVE_MODEL",
        "thinking_config": "OPENAI_NATIVE_THINKING_CONFIG",
    },
    "agnes": {
        "api_key": "AGNES_API_KEY",
        "base_url": "AGNES_BASE_URL",
        "model": "AGNES_MODEL",
        "thinking_config": "AGNES_THINKING_CONFIG",
    },
    "claude": {
        "api_key": "CLAUDE_API_KEY",
        "base_url": "CLAUDE_BASE_URL",
        "model": "CLAUDE_MODEL",
        "thinking_config": "CLAUDE_THINKING_CONFIG",
    },
    "kimi": {
        "api_key": "KIMI_API_KEY",
        "base_url": "KIMI_BASE_URL",
        "model": "KIMI_MODEL",
        "thinking_config": "KIMI_THINKING_CONFIG",
    },
    "siliconflow": {
        "api_key": "SILICONFLOW_API_KEY",
        "base_url": "SILICONFLOW_BASE_URL",
        "model": "SILICONFLOW_MODEL",
        "thinking_config": "SILICONFLOW_THINKING_CONFIG",
    },
    "zhipu": {
        "api_key": "ZHIPU_API_KEY",
        "base_url": "ZHIPU_BASE_URL",
        "model": "ZHIPU_MODEL",
        "thinking_config": "ZHIPU_THINKING_CONFIG",
    },
}


PROVIDER_THINKING_SETTINGS_FIELDS = {
    "dashscope": "dashscope_thinking_config",
    "deepseek": "deepseek_thinking_config",
    "openai": "openai_native_thinking_config",
    "agnes": "agnes_thinking_config",
    "claude": "claude_thinking_config",
    "kimi": "kimi_thinking_config",
    "siliconflow": "siliconflow_thinking_config",
    "zhipu": "zhipu_thinking_config",
}

PROVIDER_THINKING_TEMPLATES = {
    "dashscope": {"enable_thinking": True},
    "deepseek": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "openai": {"reasoning_effort": "medium"},
    "agnes": {},
    "claude": {"thinking": {"type": "enabled", "budget_tokens": 2000}},
    "kimi": {},
    "siliconflow": {"enable_thinking": True},
    "zhipu": {"thinking": {"type": "enabled"}},
}


def _normalize_provider(provider: Optional[str]) -> str:
    if not provider:
        return _current_default_llm_provider()
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_LLM_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {provider}")
    return normalized


def _current_default_llm_provider() -> str:
    return (
        settings.llm_provider
        if settings.llm_provider in SUPPORTED_LLM_PROVIDERS
        else "dashscope"
    )


def _resolve_llm_config(provider: Optional[str] = None) -> Dict[str, str]:
    normalized = _normalize_provider(provider)
    meta = PROVIDER_META.get(normalized)
    if not meta:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {normalized}")
    return {
        "provider": normalized,
        "provider_label": meta["label"],
        "api_key": meta["api_key"](),
        "base_url": meta["base_url"](),
        "model": meta["model"](),
        "thinking_config": _get_provider_thinking_config(normalized),
    }


def _get_provider_thinking_template(provider: str) -> dict:
    return dict(PROVIDER_THINKING_TEMPLATES.get(provider, {}))


def _parse_thinking_config(raw_config) -> dict:
    if raw_config in (None, ""):
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    try:
        parsed = json.loads(str(raw_config))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="思考配置 JSON 格式错误") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="思考配置必须是 JSON 对象")
    return parsed


def _get_provider_thinking_config(provider: str) -> dict:
    field = PROVIDER_THINKING_SETTINGS_FIELDS.get(provider)
    if not field:
        return {}
    return _parse_thinking_config(getattr(settings, field, ""))
