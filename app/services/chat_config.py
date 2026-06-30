"""Chat provider and web-search configuration helpers."""

import json
from typing import Callable, Dict, Optional

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import UserApiAccount
from app.services.api_credentials import (
    LLM_API_SOURCE_OFFICIAL,
    LLM_API_SOURCE_PERSONAL,
    normalize_llm_api_source,
    provider_defaults,
)
from app.services.chat_config_env import (
    SETTINGS_FIELD_BY_ENV,
    _env_file_path,
    _read_env_values,
    _write_env_values,
)

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


def current_user_llm_source(
    user,
    *,
    has_personal: bool,
    has_official: bool,
) -> str:
    preferred = normalize_llm_api_source(
        getattr(user, "llm_api_source", None),
        default=None,
    )
    if preferred:
        return preferred
    if has_personal:
        return LLM_API_SOURCE_PERSONAL
    if has_official:
        return LLM_API_SOURCE_OFFICIAL
    return LLM_API_SOURCE_PERSONAL


async def llm_config_response(
    current_user,
    db: AsyncSession,
    *,
    resolve_llm_config=_resolve_llm_config,
    current_default_llm_provider=_current_default_llm_provider,
    get_provider_thinking_template=_get_provider_thinking_template,
) -> dict:
    result = await db.execute(
        select(UserApiAccount)
        .where(
            UserApiAccount.user_id == current_user.id,
            UserApiAccount.provider.in_(SUPPORTED_LLM_PROVIDERS),
        )
        .order_by(UserApiAccount.is_default.desc(), UserApiAccount.created_at.asc())
    )
    user_accounts = result.scalars().all()
    account_by_provider: dict[str, UserApiAccount] = {}
    enabled_account_by_provider: dict[str, UserApiAccount] = {}
    for account in user_accounts:
        account_by_provider.setdefault(account.provider, account)
        if account.enabled:
            enabled_account_by_provider.setdefault(account.provider, account)

    default_account = next(
        (
            account
            for account in user_accounts
            if account.enabled and account.is_default
        ),
        None,
    )
    if default_account is None:
        default_account = next(
            (account for account in user_accounts if account.enabled), None
        )
    official_config_by_provider = {
        provider: resolve_llm_config(provider) for provider in PROVIDER_META
    }
    has_personal = default_account is not None
    has_official = any(
        bool((config.get("api_key") or "").strip())
        for config in official_config_by_provider.values()
    )
    current_api_source = current_user_llm_source(
        current_user,
        has_personal=has_personal,
        has_official=has_official,
    )
    current_provider = (
        default_account.provider
        if current_api_source == LLM_API_SOURCE_PERSONAL and default_account
        else current_default_llm_provider()
    )

    providers = []
    for provider, meta in PROVIDER_META.items():
        account = account_by_provider.get(provider)
        enabled_account = enabled_account_by_provider.get(provider)
        defaults = provider_defaults(provider)
        official_config = official_config_by_provider[provider]
        official_enabled = bool((official_config.get("api_key") or "").strip())
        personal_enabled = bool(enabled_account)
        selected_account = (
            enabled_account
            if current_api_source == LLM_API_SOURCE_PERSONAL
            else account
        )
        if current_api_source == LLM_API_SOURCE_OFFICIAL:
            model = official_config["model"]
            base_url = official_config["base_url"]
            thinking_config = official_config["thinking_config"]
            enabled = official_enabled
        else:
            model = selected_account.model if selected_account else defaults.model
            base_url = (
                selected_account.base_url if selected_account else defaults.base_url
            )
            thinking_config = (
                selected_account.thinking_config if selected_account else {}
            )
            enabled = personal_enabled
        providers.append(
            {
                "provider": provider,
                "label": meta["label"],
                "enabled": enabled,
                "official_enabled": official_enabled,
                "personal_enabled": personal_enabled,
                "model": model,
                "base_url": base_url,
                "thinking_config": thinking_config,
                "thinking_template": get_provider_thinking_template(provider),
            }
        )
    return {
        "current_provider": current_provider,
        "current_api_source": current_api_source,
        "providers": providers,
    }


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


def save_global_web_search_config(
    *,
    provider: str,
    tavily_api_key: Optional[str] = None,
    fallback_html: bool = True,
    tavily_search_depth: str = "basic",
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
) -> dict:
    """Persist global web-search settings without echoing saved secrets."""
    normalized_provider = _normalize_web_search_provider(provider)
    normalized_depth = _normalize_tavily_search_depth(tavily_search_depth)
    tavily_key = (tavily_api_key or "").strip()
    existing_tavily_key = settings.tavily_api_key.strip()
    if normalized_provider == "tavily" and not (tavily_key or existing_tavily_key):
        raise HTTPException(status_code=400, detail="Tavily API Key cannot be empty")

    updates = {
        "WEB_SEARCH_PROVIDER": normalized_provider,
        "WEB_SEARCH_FALLBACK_HTML": "true" if fallback_html else "false",
        "TAVILY_SEARCH_DEPTH": normalized_depth,
    }
    if tavily_key:
        updates["TAVILY_API_KEY"] = tavily_key

    env_writer(updates)
    settings.web_search_provider = normalized_provider
    settings.web_search_fallback_html = fallback_html
    settings.tavily_search_depth = normalized_depth
    if tavily_key:
        settings.tavily_api_key = tavily_key

    return _web_search_config_response(normalized_provider)


def save_global_llm_provider_config(
    *,
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    thinking_mode: str = "off",
    thinking_config: Optional[dict] = None,
    verifier: Callable[[dict], int],
    resolve_llm_config: Callable[[Optional[str]], Dict[str, str]] = _resolve_llm_config,
    get_provider_thinking_template: Callable[[str], dict] = (
        _get_provider_thinking_template
    ),
    parse_thinking_config: Callable[[object], dict] = _parse_thinking_config,
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
    reset_rag: Callable[[], None] | None = None,
    warning_logger: Callable[[str], None] = logger.warning,
    info_logger: Callable[[str], None] = logger.info,
) -> dict:
    """Validate and persist a global LLM provider configuration."""
    normalized_provider = _normalize_provider(provider)
    env_fields = PROVIDER_ENV_FIELDS.get(normalized_provider)
    if not env_fields:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型提供方: {normalized_provider}",
        )

    current = resolve_llm_config(normalized_provider)
    resolved_api_key = (api_key or "").strip() or current["api_key"]
    if not resolved_api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    normalized_thinking_mode = thinking_mode.strip().lower()
    if normalized_thinking_mode not in {"off", "standard", "custom"}:
        raise HTTPException(status_code=400, detail="不支持的思考配置模式")
    if normalized_thinking_mode == "off":
        resolved_thinking_config = {}
    elif normalized_thinking_mode == "standard":
        resolved_thinking_config = get_provider_thinking_template(normalized_provider)
        if not resolved_thinking_config:
            raise HTTPException(
                status_code=400,
                detail="该提供商没有通用标准模板，请使用自定义 JSON",
            )
    else:
        resolved_thinking_config = parse_thinking_config(thinking_config)
        if not resolved_thinking_config:
            raise HTTPException(status_code=400, detail="自定义思考配置不能为空")

    resolved_base_url = (base_url or "").strip() or current["base_url"]
    resolved_model = (model or "").strip() or current["model"]
    pending_config = {
        "provider": normalized_provider,
        "provider_label": current["provider_label"],
        "api_key": resolved_api_key,
        "base_url": resolved_base_url,
        "model": resolved_model,
        "thinking_config": resolved_thinking_config,
    }
    latency_ms = verifier(pending_config)

    env_writer(
        {
            "LLM_PROVIDER": normalized_provider,
            env_fields["api_key"]: resolved_api_key,
            env_fields["base_url"]: resolved_base_url,
            env_fields["model"]: resolved_model,
            env_fields["thinking_config"]: json.dumps(
                resolved_thinking_config,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    )

    if reset_rag is not None:
        try:
            reset_rag()
        except Exception as exc:
            warning_logger(f"重置 RAG 服务失败，将在下次重启后生效: {exc}")

    llm_config = resolve_llm_config(normalized_provider)
    info_logger(f"已保存 LLM 配置: {normalized_provider} / model={llm_config['model']}")
    return {
        "ok": True,
        "current_provider": normalized_provider,
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
        "thinking_config": llm_config["thinking_config"],
        "thinking_template": get_provider_thinking_template(normalized_provider),
        "verified": True,
        "latency_ms": latency_ms,
    }


def set_global_llm_provider(
    provider: str,
    *,
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
    resolve_llm_config: Callable[[Optional[str]], Dict[str, str]] = _resolve_llm_config,
    info_logger: Callable[[str], None] = logger.info,
) -> dict:
    """Persist the selected global LLM provider."""
    llm_config = resolve_llm_config(provider)
    if not llm_config["api_key"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{llm_config['provider_label']} API Key 未配置，"
                "请先在 .env.local 中配置后重启后端。"
            ),
        )

    env_writer({"LLM_PROVIDER": llm_config["provider"]})
    info_logger(
        f"已切换 LLM 提供方: {llm_config['provider']} / model={llm_config['model']}"
    )
    return {
        "ok": True,
        "current_provider": llm_config["provider"],
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
    }
