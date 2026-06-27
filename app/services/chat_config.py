"""Chat provider and web-search configuration helpers."""

import json
from pathlib import Path
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


SETTINGS_FIELD_BY_ENV = {
    "LLM_PROVIDER": "llm_provider",
    "DASHSCOPE_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "LLM_MODEL": "llm_model",
    "DASHSCOPE_THINKING_CONFIG": "dashscope_thinking_config",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "DEEPSEEK_MODEL": "deepseek_model",
    "DEEPSEEK_THINKING_CONFIG": "deepseek_thinking_config",
    "OPENAI_NATIVE_API_KEY": "openai_native_api_key",
    "OPENAI_NATIVE_BASE_URL": "openai_native_base_url",
    "OPENAI_NATIVE_MODEL": "openai_native_model",
    "OPENAI_NATIVE_THINKING_CONFIG": "openai_native_thinking_config",
    "KIMI_API_KEY": "kimi_api_key",
    "KIMI_BASE_URL": "kimi_base_url",
    "KIMI_MODEL": "kimi_model",
    "KIMI_THINKING_CONFIG": "kimi_thinking_config",
    "SILICONFLOW_API_KEY": "siliconflow_api_key",
    "SILICONFLOW_BASE_URL": "siliconflow_base_url",
    "SILICONFLOW_MODEL": "siliconflow_model",
    "SILICONFLOW_THINKING_CONFIG": "siliconflow_thinking_config",
    "ZHIPU_API_KEY": "zhipu_api_key",
    "ZHIPU_BASE_URL": "zhipu_base_url",
    "ZHIPU_MODEL": "zhipu_model",
    "ZHIPU_THINKING_CONFIG": "zhipu_thinking_config",
    "WEB_SEARCH_PROVIDER": "web_search_provider",
    "TAVILY_API_KEY": "tavily_api_key",
    "WEB_SEARCH_FALLBACK_HTML": "web_search_fallback_html",
    "TAVILY_SEARCH_DEPTH": "tavily_search_depth",
}

PROVIDER_THINKING_SETTINGS_FIELDS = {
    "dashscope": "dashscope_thinking_config",
    "deepseek": "deepseek_thinking_config",
    "openai": "openai_native_thinking_config",
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


def _env_file_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env.local"


def _read_env_values(path: Path) -> tuple[list[str], Dict[str, str]]:
    if not path.exists():
        return [], {}

    lines = path.read_text(encoding="utf-8").splitlines()
    values: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return lines, values


def _write_env_values(updates: Dict[str, str]) -> None:
    path = _env_file_path()
    lines, existing = _read_env_values(path)
    written = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            next_lines.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            next_lines.append(line)

    missing = [key for key in updates if key not in written and key not in existing]
    if missing and next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key in missing:
        next_lines.append(f"{key}={updates[key]}")

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in updates.items():
        field = SETTINGS_FIELD_BY_ENV.get(key)
        if field:
            setattr(settings, field, value)


SUPPORTED_WEB_SEARCH_PROVIDERS = {"auto", "tavily", "html"}
SUPPORTED_TAVILY_SEARCH_DEPTHS = {"basic", "advanced"}


def _normalize_web_search_provider(provider: Optional[str]) -> str:
    normalized = (provider or "auto").strip().lower()
    if normalized not in SUPPORTED_WEB_SEARCH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported web search provider")
    return normalized


def _normalize_tavily_search_depth(depth: Optional[str]) -> str:
    normalized = (depth or "basic").strip().lower()
    if normalized not in SUPPORTED_TAVILY_SEARCH_DEPTHS:
        raise HTTPException(status_code=400, detail="Unsupported Tavily search depth")
    return normalized


def _web_search_config_response(
    provider: str,
    *,
    tavily_configured: bool | None = None,
) -> dict:
    return {
        "provider": provider,
        "tavily_configured": (
            bool(settings.tavily_api_key.strip())
            if tavily_configured is None
            else tavily_configured
        ),
        "fallback_html": bool(settings.web_search_fallback_html),
        "tavily_search_depth": _normalize_tavily_search_depth(
            settings.tavily_search_depth
        ),
    }
