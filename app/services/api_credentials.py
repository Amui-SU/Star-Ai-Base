from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiAccountResponse, SystemUser, UsageEvent, UserApiAccount
from app.security import decrypt_text, encrypt_text
from app.time_utils import utc_now


@dataclass(frozen=True)
class ProviderDefaults:
    label: str
    base_url: str
    model: str


@dataclass(frozen=True)
class ResolvedApiCredential:
    api_source: str
    provider: str
    provider_label: str
    api_key: str
    base_url: str
    model: str
    thinking_config: dict
    account_id: int | None

    def to_llm_config(self) -> dict:
        return {
            "provider": self.provider,
            "provider_label": self.provider_label,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "thinking_config": self.thinking_config,
            "api_account_id": self.account_id,
            "api_source": self.api_source,
        }


PROVIDER_DEFAULTS: dict[str, ProviderDefaults] = {
    "dashscope": ProviderDefaults(
        label="阿里云 DashScope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-max",
    ),
    "deepseek": ProviderDefaults(
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    ),
    "openai": ProviderDefaults(
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    ),
    "kimi": ProviderDefaults(
        label="Moonshot Kimi",
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k",
    ),
    "siliconflow": ProviderDefaults(
        label="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
    ),
    "zhipu": ProviderDefaults(
        label="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-flash",
    ),
    "tavily": ProviderDefaults(
        label="Tavily",
        base_url="https://api.tavily.com",
        model="tavily-search",
    ),
}

SUPPORTED_API_PROVIDERS = set(PROVIDER_DEFAULTS)
LLM_API_SOURCE_OFFICIAL = "official"
LLM_API_SOURCE_PERSONAL = "personal"
SUPPORTED_LLM_API_SOURCES = {LLM_API_SOURCE_OFFICIAL, LLM_API_SOURCE_PERSONAL}
LLM_API_SOURCE_ALIASES = {
    "global": LLM_API_SOURCE_OFFICIAL,
    "system": LLM_API_SOURCE_OFFICIAL,
    "platform": LLM_API_SOURCE_OFFICIAL,
    "user": LLM_API_SOURCE_PERSONAL,
    "personal": LLM_API_SOURCE_PERSONAL,
}


def normalize_provider(value: str) -> str:
    provider = (value or "").strip().lower()
    if provider not in SUPPORTED_API_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 API 服务商: {value}")
    return provider


def provider_defaults(provider: str) -> ProviderDefaults:
    return PROVIDER_DEFAULTS[normalize_provider(provider)]


def normalize_llm_api_source(
    value: str | None, default: str | None = None
) -> str | None:
    source = (value or "").strip().lower()
    if not source:
        return default
    normalized = LLM_API_SOURCE_ALIASES.get(source, source)
    if normalized not in SUPPORTED_LLM_API_SOURCES:
        raise HTTPException(status_code=400, detail=f"不支持的模型来源: {value}")
    return normalized


def encrypt_api_key(api_key: str) -> str:
    secret = (api_key or "").strip()
    if not secret:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    return encrypt_text(secret)


def decrypt_api_key(encrypted: str) -> str:
    try:
        return decrypt_text(encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="API Key 解密失败") from exc


def account_response(account: UserApiAccount) -> ApiAccountResponse:
    defaults = provider_defaults(account.provider)
    return ApiAccountResponse(
        id=account.id,
        provider=account.provider,
        provider_label=defaults.label,
        display_name=account.display_name,
        base_url=account.base_url,
        model=account.model,
        thinking_config=account.thinking_config or {},
        enabled=bool(account.enabled),
        is_default=bool(account.is_default),
        configured=bool(account.api_key_encrypted),
        last_validated_at=account.last_validated_at,
        last_error=account.last_error,
    )


async def user_has_api_accounts(db: AsyncSession, user: SystemUser) -> bool:
    result = await db.execute(
        select(UserApiAccount.id).where(UserApiAccount.user_id == user.id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def ensure_single_default(
    db: AsyncSession,
    user: SystemUser,
    account: UserApiAccount,
) -> None:
    await db.execute(
        update(UserApiAccount)
        .where(
            UserApiAccount.user_id == user.id,
            UserApiAccount.id != account.id,
        )
        .values(is_default=False)
    )
    account.is_default = True


class ApiAccountRequired(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "code": "api_account_required",
                "message": "请先添加个人 AI 服务密钥，或切换到官方通道。",
            },
        )


class OfficialApiRequired(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "code": "official_api_required",
                "message": "官方模型通道暂未开通，请切换到个人密钥。",
            },
        )


def resolved_credential_from_account(account: UserApiAccount) -> ResolvedApiCredential:
    defaults = provider_defaults(account.provider)
    return ResolvedApiCredential(
        api_source=LLM_API_SOURCE_PERSONAL,
        provider=account.provider,
        provider_label=defaults.label,
        api_key=decrypt_api_key(account.api_key_encrypted),
        base_url=account.base_url,
        model=account.model,
        thinking_config=account.thinking_config or {},
        account_id=account.id,
    )


def resolved_credential_from_official_config(config: dict) -> ResolvedApiCredential:
    provider = normalize_provider(config["provider"])
    defaults = provider_defaults(provider)
    return ResolvedApiCredential(
        api_source=LLM_API_SOURCE_OFFICIAL,
        provider=provider,
        provider_label=config.get("provider_label") or defaults.label,
        api_key=config["api_key"],
        base_url=config["base_url"],
        model=config["model"],
        thinking_config=config.get("thinking_config") or {},
        account_id=None,
    )


async def _resolve_personal_llm_account(
    db: AsyncSession,
    user: SystemUser,
    provider: str | None = None,
) -> UserApiAccount | None:
    conditions = [
        UserApiAccount.user_id == user.id,
        UserApiAccount.enabled.is_(True),
        UserApiAccount.provider != "tavily",
    ]
    if provider:
        conditions.append(UserApiAccount.provider == normalize_provider(provider))

    result = await db.execute(
        select(UserApiAccount)
        .where(*conditions)
        .order_by(UserApiAccount.is_default.desc(), UserApiAccount.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def resolve_user_llm_credentials(
    db: AsyncSession,
    user: SystemUser,
    provider: str | None = None,
    global_config_resolver=None,
) -> ResolvedApiCredential:
    preferred_source = normalize_llm_api_source(
        getattr(user, "llm_api_source", None),
        default=None,
    )

    if preferred_source == LLM_API_SOURCE_OFFICIAL:
        if global_config_resolver is None:
            raise OfficialApiRequired()
        official_config = global_config_resolver(provider)
        if not (official_config.get("api_key") or "").strip():
            raise OfficialApiRequired()
        return resolved_credential_from_official_config(official_config)

    account = await _resolve_personal_llm_account(db, user, provider)
    if account is not None:
        return resolved_credential_from_account(account)

    if preferred_source == LLM_API_SOURCE_PERSONAL:
        raise ApiAccountRequired()

    if global_config_resolver is not None:
        official_config = global_config_resolver(provider)
        if (official_config.get("api_key") or "").strip():
            return resolved_credential_from_official_config(official_config)

    raise ApiAccountRequired()


async def resolve_optional_user_api_credentials(
    db: AsyncSession,
    user: SystemUser,
    provider: str,
) -> ResolvedApiCredential | None:
    normalized_provider = normalize_provider(provider)
    result = await db.execute(
        select(UserApiAccount)
        .where(
            UserApiAccount.user_id == user.id,
            UserApiAccount.enabled.is_(True),
            UserApiAccount.provider == normalized_provider,
        )
        .order_by(UserApiAccount.is_default.desc(), UserApiAccount.created_at.asc())
        .limit(1)
    )
    account = result.scalar_one_or_none()
    if account is None:
        return None
    return resolved_credential_from_account(account)


async def record_usage_event(
    db: AsyncSession,
    *,
    user: SystemUser,
    credential: ResolvedApiCredential,
    feature: str,
    status: str = "success",
    error_code: str | None = None,
) -> None:
    db.add(
        UsageEvent(
            user_id=user.id,
            api_account_id=credential.account_id,
            api_source=credential.api_source,
            feature=feature,
            provider=credential.provider,
            model=credential.model,
            status=status,
            error_code=error_code,
        )
    )
