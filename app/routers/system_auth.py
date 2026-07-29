import httpx
from fastapi import APIRouter, Depends, Request, Response
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from app.database import get_db
from app.models import (
    AdminPasswordResetResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdateRequest,
    PasswordResetSendCodeRequest,
    SystemAuthResponse,
    SystemDisplayNameUpdateRequest,
    SystemLoginRequest,
    SystemRegisterRequest,
    SystemUserResponse,
)
from app.services.system_auth_account import (
    current_system_user_response,
    logout_system_user,
    update_system_display_name,
)
from app.services.system_auth_admin import (
    get_current_admin_user as _get_current_admin_user,
    list_admin_users as _list_admin_users,
    reset_admin_user_password as _reset_admin_user_password,
    update_admin_user_status as _update_admin_user_status,
)
from app.services.system_auth_codes import (
    CODE_TTL_SECONDS as _CODE_TTL_SECONDS,
    IP_RATE_MAX as _IP_RATE_MAX,
    IP_RATE_WINDOW as _IP_RATE_WINDOW,
    MAX_ATTEMPTS as _MAX_ATTEMPTS,
    check_ip_rate_limit as _check_ip_rate_limit,
    check_rate_limit as _check_rate_limit,
    hash_code as _hash_code,
    ip_rate_limit as _ip_rate_limit,
    password_exceeds_bcrypt_limit as _password_exceeds_bcrypt_limit,
    send_verification_code as _send_verification_code,
)
from app.services.system_auth_callback_runtime import (
    email_config_status as _email_config_status,
    handle_google_oauth_callback as _handle_google_oauth_callback,
    handle_qq_oauth_callback as _handle_qq_oauth_callback,
    handle_wechat_oauth_callback as _handle_wechat_oauth_callback,
)
from app.services.system_auth_login import (
    login_system_user,
)
from app.services.system_auth_password_reset import (
    send_password_reset_code as _send_password_reset_code,
)
from app.services.system_auth_registration import (
    register_system_user,
)
from app.services.system_auth_oauth import (
    OAUTH_STATE_COOKIE_NAME,
    clear_oauth_state_cookie as _clear_oauth_state_cookie,
    decode_oauth_state as _decode_oauth_state,
    frontend_origin_is_allowed as _frontend_origin_is_allowed,
    frontend_url_from_request as _frontend_url_from_request,
    frontend_url_from_state as _frontend_url_from_state,
    make_oauth_state as _make_oauth_state,
    new_oauth_state_nonce as _new_oauth_state_nonce,
    normalize_frontend_origin as _normalize_frontend_origin,
    oauth_signing_key as _oauth_signing_key,
    oauth_state_nonce_is_valid as _oauth_state_nonce_is_valid,
    oauth_user_email as _oauth_user_email,
    set_oauth_state_cookie as _set_oauth_state_cookie,
    verify_oauth_state as _verify_oauth_state,
)
from app.services.system_auth_oauth_flow import (
    build_google_login_redirect as _build_google_login_redirect,
    build_qq_login_redirect as _build_qq_login_redirect,
    build_wechat_login_redirect as _build_wechat_login_redirect,
    qq_redirect_uri as _qq_redirect_uri,
    redirect_with_oauth_session as _redirect_with_oauth_session,
    upsert_oauth_user as _upsert_oauth_user,
    validate_oauth_callback_state as _validate_oauth_callback_state,
    wechat_redirect_uri as _wechat_redirect_uri,
)
from app.services.system_auth_oauth_providers import (
    fetch_google_oauth_user as _fetch_google_oauth_user,
    fetch_qq_oauth_user as _fetch_qq_oauth_user,
    fetch_wechat_oauth_user as _fetch_wechat_oauth_user,
)

router = APIRouter(prefix="/system-auth", tags=["系统认证"])


class SendCodeRequest(BaseModel):
    email: str


@router.post("/send-code")
async def send_verification_code(
    payload: SendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """发送邮箱验证码。DEBUG 模式下验证码直接返回，生产模式通过 SMTP 发送邮件。"""
    client_ip = request.client.host if request.client else "unknown"
    return await _send_verification_code(
        db,
        email=payload.email,
        client_ip=client_ip,
        debug=bool(settings.debug),
    )


@router.post("/register", response_model=SystemAuthResponse)
async def register(
    payload: SystemRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    return await register_system_user(db, payload=payload, response=response)


@router.post("/login", response_model=SystemAuthResponse)
async def login(
    payload: SystemLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    return await login_system_user(db, payload=payload, response=response)


@router.post("/password-reset/send-code")
async def send_password_reset_code(
    payload: PasswordResetSendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    return await _send_password_reset_code(
        db,
        email=payload.email,
        client_ip=client_ip,
        debug=bool(settings.debug),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await logout_system_user(db, request=request, response=response)


@router.get("/me", response_model=SystemUserResponse)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    return await current_system_user_response(db, request=request)


@router.put("/me/display-name", response_model=SystemUserResponse)
async def update_display_name(
    payload: SystemDisplayNameUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    return await update_system_display_name(db, payload=payload, request=request)


@router.get("/admin/users", response_model=AdminUserListResponse)
async def admin_list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    await _get_current_admin_user(request, db)
    return await _list_admin_users(db)


@router.put("/admin/users/{user_id}/status", response_model=AdminUserResponse)
async def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    admin = await _get_current_admin_user(request, db)
    return await _update_admin_user_status(db, admin, user_id, payload.status)


@router.post(
    "/admin/users/{user_id}/reset-password",
    response_model=AdminPasswordResetResponse,
)
async def admin_reset_user_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminPasswordResetResponse:
    admin = await _get_current_admin_user(request, db)
    return await _reset_admin_user_password(db, admin, user_id)


# ── Google OAuth ──────────────────────────────────────────────


@router.get("/email/config")
async def email_config_status() -> dict[str, bool]:
    return _email_config_status(
        debug=bool(settings.debug),
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
    )


@router.get("/wechat/login")
async def wechat_login(request: Request, frontend_url: str = ""):
    return _build_wechat_login_redirect(request, frontend_url)


@router.get("/qq/login")
async def qq_login(request: Request, frontend_url: str = ""):
    return _build_qq_login_redirect(request, frontend_url)


@router.get("/wechat/callback")
async def wechat_callback(
    request: Request,
    code: str = "",
    error: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    return await _handle_wechat_oauth_callback(
        request=request,
        code=code,
        error=error,
        state=state,
        db=db,
        settings=settings,
        async_client_factory=httpx.AsyncClient,
        validate_oauth_callback_state=_validate_oauth_callback_state,
        fetch_wechat_oauth_user=_fetch_wechat_oauth_user,
        upsert_oauth_user=_upsert_oauth_user,
        redirect_with_oauth_session=_redirect_with_oauth_session,
        wechat_redirect_uri=_wechat_redirect_uri,
        logger=logger,
    )


@router.get("/qq/callback")
async def qq_callback(
    request: Request,
    code: str = "",
    error: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    return await _handle_qq_oauth_callback(
        request=request,
        code=code,
        error=error,
        state=state,
        db=db,
        settings=settings,
        async_client_factory=httpx.AsyncClient,
        validate_oauth_callback_state=_validate_oauth_callback_state,
        fetch_qq_oauth_user=_fetch_qq_oauth_user,
        upsert_oauth_user=_upsert_oauth_user,
        redirect_with_oauth_session=_redirect_with_oauth_session,
        qq_redirect_uri=_qq_redirect_uri,
        logger=logger,
    )


@router.get("/google/login")
async def google_login(request: Request, frontend_url: str = ""):
    """重定向到 Google OAuth 授权页面。"""
    return _build_google_login_redirect(request, frontend_url)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = "",
    error: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Google OAuth 回调：用 code 换 token，获取用户信息，创建或登录。"""
    return await _handle_google_oauth_callback(
        request=request,
        code=code,
        error=error,
        state=state,
        db=db,
        settings=settings,
        async_client_factory=httpx.AsyncClient,
        validate_oauth_callback_state=_validate_oauth_callback_state,
        fetch_google_oauth_user=_fetch_google_oauth_user,
        upsert_oauth_user=_upsert_oauth_user,
        redirect_with_oauth_session=_redirect_with_oauth_session,
        logger=logger,
    )
