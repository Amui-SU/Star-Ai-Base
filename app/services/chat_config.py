"""Chat provider and web-search configuration helpers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.chat_provider_catalog import (
    PROVIDER_ENV_FIELDS,
    PROVIDER_META,
    PROVIDER_THINKING_SETTINGS_FIELDS,
    PROVIDER_THINKING_TEMPLATES,
    SUPPORTED_LLM_PROVIDERS,
    _current_default_llm_provider,
    _get_provider_thinking_config,
    _get_provider_thinking_template,
    _normalize_provider,
    _parse_thinking_config,
    _resolve_llm_config,
)
from app.services.chat_provider_config import (
    save_global_llm_provider_config,
    set_global_llm_provider,
)
from app.services.chat_web_search_config import (
    SUPPORTED_TAVILY_SEARCH_DEPTHS,
    SUPPORTED_WEB_SEARCH_PROVIDERS,
    _normalize_tavily_search_depth,
    _normalize_web_search_provider,
    _web_search_config_response,
    save_global_web_search_config,
)


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
