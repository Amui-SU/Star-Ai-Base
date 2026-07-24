"""Validation and persistence mapping for user-owned API accounts."""

from fastapi import HTTPException

from app.models import ApiAccountCreateRequest, ApiAccountUpdateRequest, UserApiAccount
from app.services.api_account_config import (
    ProviderPreset,
    normalize_advanced_config,
    normalize_provider,
    provider_defaults,
)
from app.services.api_credentials import encrypt_api_key


def _required_text(value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field} cannot be empty")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _validate_protocol_and_auth(
    preset: ProviderPreset,
    protocol: str | None,
    auth_scheme: str | None,
) -> tuple[str | None, str | None]:
    normalized_protocol = _optional_text(protocol)
    normalized_auth = _optional_text(auth_scheme)
    if normalized_protocol not in {None, "openai_compatible", "anthropic_messages"}:
        raise HTTPException(status_code=400, detail="Unsupported API protocol")
    if normalized_auth not in {None, "bearer", "x_api_key"}:
        raise HTTPException(status_code=400, detail="Unsupported API auth scheme")
    if normalized_protocol != preset.protocol or normalized_auth != preset.auth_scheme:
        raise HTTPException(
            status_code=400,
            detail="Protocol and auth scheme are incompatible with provider",
        )
    return normalized_protocol, normalized_auth


def _normalized_advanced(value: object, model: str) -> dict:
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid advanced_config")
    normalized = normalize_advanced_config(value, model)
    normalized["fallback_model"] = model
    return normalized


def build_api_account(
    body: ApiAccountCreateRequest,
    *,
    user_id: int,
    is_default: bool,
) -> UserApiAccount:
    provider = normalize_provider(body.provider)
    preset = provider_defaults(provider)
    protocol, auth_scheme = _validate_protocol_and_auth(
        preset,
        body.protocol if body.protocol is not None else preset.protocol,
        body.auth_scheme if body.auth_scheme is not None else preset.auth_scheme,
    )
    model = _required_text(body.model or preset.model, "Model")
    return UserApiAccount(
        user_id=user_id,
        provider=provider,
        display_name=_required_text(body.display_name or preset.label, "Display name"),
        api_key_encrypted=encrypt_api_key(body.api_key),
        base_url=_required_text(body.base_url or preset.base_url, "Base URL"),
        model=model,
        thinking_config=body.thinking_config or {},
        protocol=protocol,
        auth_scheme=auth_scheme,
        website_url=_optional_text(body.website_url) or preset.website_url,
        notes=body.notes,
        advanced_config=_normalized_advanced(body.advanced_config, model),
        enabled=True,
        is_default=is_default,
    )


def apply_api_account_update(
    account: UserApiAccount,
    body: ApiAccountUpdateRequest,
) -> None:
    preset = provider_defaults(account.provider)
    fields = body.model_fields_set
    if "display_name" in fields:
        account.display_name = _required_text(body.display_name, "Display name")
    if "api_key" in fields and (body.api_key or "").strip():
        account.api_key_encrypted = encrypt_api_key(body.api_key or "")
        account.last_error = None
    if "base_url" in fields:
        account.base_url = _required_text(body.base_url, "Base URL")

    protocol = getattr(account, "protocol", None) or preset.protocol
    auth_scheme = getattr(account, "auth_scheme", None) or preset.auth_scheme
    if "protocol" in fields:
        protocol = body.protocol
    if "auth_scheme" in fields:
        auth_scheme = body.auth_scheme
    account.protocol, account.auth_scheme = _validate_protocol_and_auth(
        preset, protocol, auth_scheme
    )

    if "website_url" in fields:
        account.website_url = _optional_text(body.website_url)
    elif getattr(account, "website_url", None) is None:
        account.website_url = preset.website_url
    if "notes" in fields:
        account.notes = body.notes
    if "thinking_config" in fields:
        account.thinking_config = body.thinking_config or {}

    model = account.model
    if "model" in fields:
        model = _required_text(body.model, "Model")
    if "advanced_config" in fields and body.advanced_config is not None:
        advanced = normalize_advanced_config(body.advanced_config, model)
        if "model" not in fields and advanced["fallback_model"]:
            model = advanced["fallback_model"]
    else:
        advanced = normalize_advanced_config(
            getattr(account, "advanced_config", None), model
        )
    advanced["fallback_model"] = model
    account.model = model
    account.advanced_config = advanced

    if body.enabled is not None:
        account.enabled = body.enabled
