from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    ApiAccountCreateRequest,
    ApiAccountResponse,
    ApiAccountUpdateRequest,
    SystemUser,
    UserApiAccount,
)
from app.services.api_credentials import (
    account_response,
    encrypt_api_key,
    ensure_single_default,
    normalize_provider,
    provider_defaults,
    user_has_api_accounts,
    utc_now,
)

router = APIRouter(prefix="/api-accounts", tags=["api-accounts"])


async def _get_user_account(
    db: AsyncSession,
    user: SystemUser,
    account_id: int,
) -> UserApiAccount:
    result = await db.execute(
        select(UserApiAccount).where(
            UserApiAccount.id == account_id,
            UserApiAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="AI 服务密钥不存在")
    return account


@router.get("", response_model=list[ApiAccountResponse])
@router.get("/", response_model=list[ApiAccountResponse])
async def list_api_accounts(
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserApiAccount)
        .where(UserApiAccount.user_id == current_user.id)
        .order_by(UserApiAccount.is_default.desc(), UserApiAccount.created_at.asc())
    )
    return [account_response(account) for account in result.scalars().all()]


@router.post("", response_model=ApiAccountResponse)
@router.post("/", response_model=ApiAccountResponse)
async def create_api_account(
    body: ApiAccountCreateRequest,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    provider = normalize_provider(body.provider)
    defaults = provider_defaults(provider)
    has_accounts = await user_has_api_accounts(db, current_user)
    account = UserApiAccount(
        user_id=current_user.id,
        provider=provider,
        display_name=(body.display_name or defaults.label).strip() or defaults.label,
        api_key_encrypted=encrypt_api_key(body.api_key),
        base_url=(body.base_url or defaults.base_url).strip() or defaults.base_url,
        model=(body.model or defaults.model).strip() or defaults.model,
        thinking_config=body.thinking_config or {},
        enabled=True,
        is_default=body.is_default or not has_accounts,
    )
    db.add(account)
    await db.flush()
    if account.is_default:
        await ensure_single_default(db, current_user, account)
    await db.commit()
    await db.refresh(account)
    return account_response(account)


@router.patch("/{account_id}", response_model=ApiAccountResponse)
async def update_api_account(
    account_id: int,
    body: ApiAccountUpdateRequest,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, current_user, account_id)
    if body.display_name is not None:
        display_name = body.display_name.strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="密钥名称不能为空")
        account.display_name = display_name
    if body.api_key is not None:
        account.api_key_encrypted = encrypt_api_key(body.api_key)
        account.last_error = None
    if body.base_url is not None:
        base_url = body.base_url.strip()
        if not base_url:
            raise HTTPException(status_code=400, detail="Base URL 不能为空")
        account.base_url = base_url
    if body.model is not None:
        model = body.model.strip()
        if not model:
            raise HTTPException(status_code=400, detail="模型不能为空")
        account.model = model
    if body.thinking_config is not None:
        account.thinking_config = body.thinking_config
    if body.enabled is not None:
        account.enabled = body.enabled
    if body.is_default is True:
        await ensure_single_default(db, current_user, account)
    elif body.is_default is False:
        account.is_default = False

    await db.commit()
    await db.refresh(account)
    return account_response(account)


@router.post("/{account_id}/set-default", response_model=ApiAccountResponse)
async def set_default_api_account(
    account_id: int,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, current_user, account_id)
    if not account.enabled:
        raise HTTPException(status_code=400, detail="不能将停用密钥设为默认")
    await ensure_single_default(db, current_user, account)
    await db.commit()
    await db.refresh(account)
    return account_response(account)


@router.post("/{account_id}/validate", response_model=ApiAccountResponse)
async def validate_api_account(
    account_id: int,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, current_user, account_id)
    account.last_validated_at = utc_now()
    account.last_error = None
    await db.commit()
    await db.refresh(account)
    return account_response(account)


@router.delete("/{account_id}", status_code=204)
async def delete_api_account(
    account_id: int,
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, current_user, account_id)
    await db.delete(account)
    await db.commit()
    return Response(status_code=204)
