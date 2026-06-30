import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from app.database import get_db
from app.models import (
    AdminPasswordResetResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdateRequest,
    SystemAuthResponse,
    SystemDisplayNameUpdateRequest,
    SystemLoginRequest,
    SystemRegisterRequest,
    SystemSession,
    SystemUser,
    SystemUserResponse,
    Workspace,
    WorkspaceMember,
    WorkspaceResponse,
)
from app.services.system_auth_admin import (
    get_current_admin_user as _get_current_admin_user,
    is_admin_user as _is_admin_user,
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
    email_is_valid,
    hash_code as _hash_code,
    ip_rate_limit as _ip_rate_limit,
    password_exceeds_bcrypt_limit as _password_exceeds_bcrypt_limit,
    send_verification_code as _send_verification_code,
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
from app.services.system_auth_sessions import (
    create_system_session as _create_system_session,
    get_current_user as _get_current_user,
    get_primary_workspace as _get_primary_workspace,
    session_token_from_request as _session_token_from_request,
)
from app.security import (
    clear_session_cookie,
    hash_token,
    verify_password,
)
from app.time_utils import utc_now_naive

router = APIRouter(prefix="/system-auth", tags=["系统认证"])


class SendCodeRequest(BaseModel):
    email: str


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(status_code=401, detail="邮箱或密码错误")


async def _user_response(db: AsyncSession, user: SystemUser) -> SystemUserResponse:
    return SystemUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        is_admin=await _is_admin_user(db, user),
    )


def _workspace_response(
    workspace: Workspace, member: WorkspaceMember
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=member.role,
    )


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
    email = payload.email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    result = await db.execute(select(SystemUser).where(SystemUser.email == email))
    user = result.scalar_one_or_none()

    if (
        user is None
        or user.status != "active"
        or _password_exceeds_bcrypt_limit(payload.password)
        or not verify_password(payload.password, user.password_hash)
    ):
        raise _invalid_credentials_exception()

    workspace, member = await _get_primary_workspace(db, user.id)
    token = await _create_system_session(db, user.id, response)
    await db.commit()

    return SystemAuthResponse(
        user=await _user_response(db, user),
        workspace=_workspace_response(workspace, member),
        session_token=token,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = _session_token_from_request(request)
    if token:
        result = await db.execute(
            select(SystemSession).where(
                SystemSession.session_token_hash == hash_token(token)
            )
        )
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = utc_now_naive()
            await db.commit()

    clear_session_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=SystemUserResponse)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    user = await _get_current_user(request, db)
    return await _user_response(db, user)


@router.put("/me/display-name", response_model=SystemUserResponse)
async def update_display_name(
    payload: SystemDisplayNameUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    user = await _get_current_user(request, db)
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(display_name) > 100:
        raise HTTPException(status_code=400, detail="用户名不能超过 100 个字符")

    user.display_name = display_name
    await db.commit()
    await db.refresh(user)
    return await _user_response(db, user)


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
    smtp_configured = bool(settings.smtp_user and settings.smtp_password)
    return {
        "debug": bool(settings.debug),
        "smtp_configured": smtp_configured,
        "email_login_available": bool(settings.debug or smtp_configured),
    }


def _oauth_network_error(provider: str, exc: httpx.HTTPError) -> HTTPException:
    logger.error(f"{provider} OAuth network request failed: {type(exc).__name__}")
    return HTTPException(
        status_code=502,
        detail=f"Cannot connect to {provider} OAuth service",
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
    if error:
        raise HTTPException(
            status_code=400, detail=f"WeChat authorization failed: {error}"
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if (
        not settings.wechat_client_id
        or not settings.wechat_client_secret
        or not _wechat_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="WeChat login is not configured")
    state_data = await _validate_oauth_callback_state(request, state)

    try:
        oauth_user = await _fetch_wechat_oauth_user(
            code, async_client_factory=httpx.AsyncClient
        )
    except httpx.HTTPError as e:
        raise _oauth_network_error("WeChat", e) from e
    except HTTPException:
        raise

    openid = oauth_user["openid"]
    user_info = oauth_user["user_info"]
    external_id = user_info.get("openid") or openid
    user = await _upsert_oauth_user(
        db,
        "wechat",
        external_id,
        user_info.get("nickname") or "WeChat User",
        user_info.get("headimgurl") or None,
    )
    return await _redirect_with_oauth_session(db, user, state_data.get("frontend_url"))


@router.get("/qq/callback")
async def qq_callback(
    request: Request,
    code: str = "",
    error: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"QQ authorization failed: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if (
        not settings.qq_client_id
        or not settings.qq_client_secret
        or not _qq_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="QQ login is not configured")
    state_data = await _validate_oauth_callback_state(request, state)

    try:
        oauth_user = await _fetch_qq_oauth_user(
            code,
            state_data,
            async_client_factory=httpx.AsyncClient,
        )
    except httpx.HTTPError as e:
        raise _oauth_network_error("QQ", e) from e
    except HTTPException:
        raise

    openid = oauth_user["openid"]
    user_info = oauth_user["user_info"]
    user = await _upsert_oauth_user(
        db,
        "qq",
        openid,
        user_info.get("nickname") or "QQ User",
        user_info.get("figureurl_qq_2") or user_info.get("figureurl_qq_1") or None,
    )
    return await _redirect_with_oauth_session(db, user, state_data.get("frontend_url"))


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
    if error:
        raise HTTPException(status_code=400, detail=f"Google 授权失败: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="缺少授权码")
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=501, detail="Google 登录未配置")

    # 校验 state（自包含签名，无需服务端存储）
    state_data = await _validate_oauth_callback_state(request, state)

    try:
        user_info = await _fetch_google_oauth_user(
            code,
            state_data,
            async_client_factory=httpx.AsyncClient,
        )
    except httpx.HTTPError as e:
        raise _oauth_network_error("Google", e) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Google OAuth httpx 阶段异常: {type(e).__name__}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(e).__name__}"
        )

    try:
        # 校验邮箱已验证
        if not user_info.get("verified_email", False):
            raise HTTPException(status_code=400, detail="Google 邮箱未验证，无法注册")

        email = (user_info.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Google 账号未返回邮箱")

        name = user_info.get("name") or email.split("@")[0]
        picture = user_info.get("picture") or ""

        user = await _upsert_oauth_user(
            db,
            "google",
            email,
            name,
            picture or None,
            email=email,
            update_default_display_name=False,
        )
        return await _redirect_with_oauth_session(
            db, user, state_data.get("frontend_url")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Google OAuth 回调异常: {type(e).__name__}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(e).__name__}"
        )
