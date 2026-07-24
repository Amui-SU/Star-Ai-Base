"""Validate unsaved API account drafts without mutating persistence state."""

import asyncio
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApiAccountCreateRequest,
    ApiAccountDraftValidationRequest,
    ApiAccountDraftValidationResponse,
    SystemUser,
    UserApiAccount,
)
from app.services.api_account_persistence import build_api_account
from app.services.api_account_requests import build_account_request_options
from app.services.api_credentials import (
    decrypt_api_key,
    resolved_credential_from_account,
)
from app.services.llm_client import get_llm_client


def _result(
    status: str,
    *,
    latency_ms: int,
    http_status: int | None = None,
) -> ApiAccountDraftValidationResponse:
    messages = {
        "success": "Connection succeeded",
        "authentication_failed": "Authentication failed",
        "endpoint_unreachable": "Endpoint is unreachable",
        "timeout": "Connection timed out",
        "model_unavailable": "Model is unavailable",
        "invalid_configuration": "Configuration is invalid",
    }
    sections = {
        "success": "connection",
        "authentication_failed": "authentication",
        "endpoint_unreachable": "endpoint",
        "timeout": "endpoint",
        "model_unavailable": "model",
        "invalid_configuration": "configuration",
    }
    return ApiAccountDraftValidationResponse(
        status=status,
        message=messages[status],
        http_status=http_status,
        section=sections[status],
        latency_ms=latency_ms,
    )


def _status_code(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _classify(error: Exception, latency_ms: int) -> ApiAccountDraftValidationResponse:
    name = type(error).__name__.lower()
    status = _status_code(error)
    if status in {401, 403} or "authentication" in name or "permissiondenied" in name:
        return _result(
            "authentication_failed", latency_ms=latency_ms, http_status=status
        )
    if status == 404 or "notfound" in name:
        return _result("model_unavailable", latency_ms=latency_ms, http_status=status)
    if "timeout" in name:
        return _result("timeout", latency_ms=latency_ms, http_status=status)
    if "connection" in name:
        return _result(
            "endpoint_unreachable", latency_ms=latency_ms, http_status=status
        )
    if status == 400 or "badrequest" in name:
        return _result(
            "invalid_configuration", latency_ms=latency_ms, http_status=status
        )
    return _result("endpoint_unreachable", latency_ms=latency_ms, http_status=status)


async def _owned_account(
    db: AsyncSession, user: SystemUser, account_id: int
) -> UserApiAccount:
    result = await db.execute(
        select(UserApiAccount).where(
            UserApiAccount.id == account_id,
            UserApiAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="API account not found")
    return account


def _probe(config: dict[str, Any]) -> None:
    client = get_llm_client(config)
    try:
        options = build_account_request_options(config)
        extra_body = options.get("extra_body")
        if isinstance(extra_body, dict) and "max_tokens" in extra_body:
            extra_body.pop("max_tokens")
        client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            stream=False,
            **options,
        )
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            close()


async def validate_api_account_draft(
    db: AsyncSession,
    user: SystemUser,
    body: ApiAccountDraftValidationRequest,
) -> ApiAccountDraftValidationResponse:
    started = time.perf_counter()
    key = (body.api_key or "").strip()
    if body.account_id is not None:
        account = await _owned_account(db, user, body.account_id)
        if body.provider.strip().lower() != account.provider:
            raise HTTPException(status_code=400, detail="Provider cannot be changed")
        if not key:
            key = decrypt_api_key(account.api_key_encrypted)
    if not key:
        return _result("invalid_configuration", latency_ms=0)

    try:
        create_body = ApiAccountCreateRequest(
            **body.model_dump(exclude={"account_id", "api_key"}), api_key=key
        )
        draft = build_api_account(create_body, user_id=user.id, is_default=False)
        credential = resolved_credential_from_account(draft)
        config = credential.to_llm_config()
    except HTTPException:
        return _result(
            "invalid_configuration",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        await asyncio.to_thread(_probe, config)
    except Exception as error:
        return _classify(
            error,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    return _result("success", latency_ms=int((time.perf_counter() - started) * 1000))
