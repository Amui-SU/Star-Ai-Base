import hashlib
import ipaddress
import os
import secrets
import time
from datetime import timedelta

import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
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
    VerificationCode,
    VerificationIpRateLimit,
    Workspace,
    WorkspaceMember,
    WorkspaceResponse,
)
from app.services.email import send_verification_email
from app.security import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session_token,
    hash_password,
    hash_token,
    session_expires_at,
    set_session_cookie,
    verify_password,
)
from app.time_utils import as_aware_utc, utc_now, utc_now_naive

router = APIRouter(prefix="/system-auth", tags=["系统认证"])

MAX_BCRYPT_PASSWORD_BYTES = 72
_EMAIL_RE = __import__("re").compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
_CODE_TTL_SECONDS = 300  # 5 分钟有效
_MAX_ATTEMPTS = 5  # 验证码最多错误尝试次数

# IP 级别频率限制（数据库为事实源；内存字典保留给旧测试/诊断兼容）
_ip_rate_limit: dict[str, tuple[int, float]] = {}  # ip -> (count, window_start)
_IP_RATE_MAX = 3  # 每窗口最多 3 次
_IP_RATE_WINDOW = 60  # 窗口 60 秒


def _cleanup_rate_limits():
    now = time.time()
    expired = [
        ip for ip, (_, start) in _ip_rate_limit.items() if now - start > _IP_RATE_WINDOW
    ]
    for ip in expired:
        del _ip_rate_limit[ip]


def _check_rate_limit(client_ip: str) -> bool:
    """检查 IP 频率限制，超限返回 False"""
    _cleanup_rate_limits()
    entry = _ip_rate_limit.get(client_ip)
    now = time.time()
    if entry is None:
        _ip_rate_limit[client_ip] = (1, now)
        return True
    count, start = entry
    if now - start > _IP_RATE_WINDOW:
        _ip_rate_limit[client_ip] = (1, now)
        return True
    if count >= _IP_RATE_MAX:
        return False
    _ip_rate_limit[client_ip] = (count + 1, start)
    return True


async def _check_ip_rate_limit(db: AsyncSession, client_ip: str) -> bool:
    """检查并持久化验证码 IP 限流窗口，避免多 worker 绕过。"""
    now_naive = utc_now_naive()
    window_expires_before = now_naive - timedelta(seconds=_IP_RATE_WINDOW)
    await db.execute(
        delete(VerificationIpRateLimit).where(
            VerificationIpRateLimit.window_start < window_expires_before
        )
    )

    result = await db.execute(
        select(VerificationIpRateLimit).where(
            VerificationIpRateLimit.ip_address == client_ip
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        db.add(
            VerificationIpRateLimit(
                ip_address=client_ip,
                count=1,
                window_start=now_naive,
                updated_at=now_naive,
            )
        )
        await db.commit()
        return True

    if entry.window_start < window_expires_before:
        entry.count = 1
        entry.window_start = now_naive
        entry.updated_at = now_naive
        await db.commit()
        return True

    if entry.count >= _IP_RATE_MAX:
        await db.commit()
        return False

    entry.count += 1
    entry.updated_at = now_naive
    await db.commit()
    return True


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class SendCodeRequest(BaseModel):
    email: str


def _password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES


def _duplicate_email_exception() -> HTTPException:
    return HTTPException(status_code=400, detail="邮箱已注册")


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(status_code=401, detail="邮箱或密码错误")


def _configured_admin_emails() -> set[str]:
    return {
        email.strip().lower()
        for email in settings.admin_emails.split(",")
        if email.strip()
    }


async def _is_admin_user(db: AsyncSession, user: SystemUser) -> bool:
    configured = _configured_admin_emails()
    if configured:
        return user.email.lower() in configured

    result = await db.execute(select(SystemUser.id).order_by(SystemUser.id).limit(1))
    first_user_id = result.scalar_one_or_none()
    return first_user_id == user.id


def _session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token

    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


async def _user_response(db: AsyncSession, user: SystemUser) -> SystemUserResponse:
    return SystemUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        is_admin=await _is_admin_user(db, user),
    )


async def _admin_user_response(db: AsyncSession, user: SystemUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        is_admin=await _is_admin_user(db, user),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _workspace_response(
    workspace: Workspace, member: WorkspaceMember
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=member.role,
    )


async def _create_system_session(
    db: AsyncSession, user_id: int, response: Response
) -> str:
    token = create_session_token()
    db.add(
        SystemSession(
            user_id=user_id,
            session_token_hash=hash_token(token),
            expires_at=session_expires_at().replace(tzinfo=None),
        )
    )
    set_session_cookie(response, token)
    return token


async def _get_primary_workspace(
    db: AsyncSession, user_id: int
) -> tuple[Workspace, WorkspaceMember]:
    result = await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(WorkspaceMember.id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return row


async def _get_current_user(request: Request, db: AsyncSession) -> SystemUser:
    token = _session_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    result = await db.execute(
        select(SystemSession).where(
            SystemSession.session_token_hash == hash_token(token)
        )
    )
    session = result.scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    if as_aware_utc(session.expires_at) <= utc_now():
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    user_result = await db.execute(
        select(SystemUser).where(SystemUser.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    session.last_seen_at = utc_now_naive()
    await db.commit()
    return user


async def _get_current_admin_user(request: Request, db: AsyncSession) -> SystemUser:
    user = await _get_current_user(request, db)
    if not await _is_admin_user(db, user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.post("/send-code")
async def send_verification_code(
    payload: SendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """发送邮箱验证码。DEBUG 模式下验证码直接返回，生产模式通过 SMTP 发送邮件。"""
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    # IP 频率限制
    client_ip = request.client.host if request.client else "unknown"
    if not await _check_ip_rate_limit(db, client_ip):
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    # 清理过期验证码
    now_naive = utc_now_naive()
    await db.execute(
        delete(VerificationCode).where(VerificationCode.expires_at < now_naive)
    )

    # 同邮箱是否已有有效验证码
    existing = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.expires_at > now_naive,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=429, detail="验证码已发送，请查收邮箱或等待过期后重试"
        )

    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = now_naive + timedelta(seconds=_CODE_TTL_SECONDS)

    db.add(
        VerificationCode(
            email=email,
            code_hash=_hash_code(code),
            expires_at=expires_at,
        )
    )
    await db.commit()

    resp: dict = {"message": "验证码已发送"}
    if settings.debug:
        resp["code"] = code
    else:
        sent = await send_verification_email(email, code)
        if not sent:
            raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return resp


@router.post("/register", response_model=SystemAuthResponse)
async def register(
    payload: SystemRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    display_name = payload.display_name.strip()

    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if _password_exceeds_bcrypt_limit(payload.password):
        raise HTTPException(status_code=400, detail="密码长度不能超过 72 字节")

    # 校验验证码
    now_naive = utc_now_naive()
    code_result = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.expires_at > now_naive,
        )
    )
    code_row = code_result.scalar_one_or_none()

    if code_row is None:
        raise HTTPException(status_code=400, detail="验证码未发送或已过期，请重新获取")

    if code_row.attempts >= _MAX_ATTEMPTS:
        await db.delete(code_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新获取")

    if not secrets.compare_digest(code_row.code_hash, _hash_code(payload.code.strip())):
        code_row.attempts += 1
        await db.commit()
        remaining = _MAX_ATTEMPTS - code_row.attempts
        raise HTTPException(
            status_code=400, detail=f"验证码错误，还剩 {remaining} 次尝试"
        )

    await db.delete(code_row)  # 验证通过后删除
    await db.commit()

    existing_result = await db.execute(
        select(SystemUser).where(SystemUser.email == email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise _duplicate_email_exception()

    try:
        user = SystemUser(
            email=email,
            password_hash=hash_password(payload.password),
            display_name=display_name,
            status="active",
        )
        db.add(user)
        await db.flush()

        workspace = Workspace(
            name=f"{display_name} 的个人空间",
            owner_user_id=user.id,
        )
        db.add(workspace)
        await db.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
        db.add(member)
        token = await _create_system_session(db, user.id, response)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _duplicate_email_exception() from None

    return SystemAuthResponse(
        user=await _user_response(db, user),
        workspace=_workspace_response(workspace, member),
        session_token=token,
    )


@router.post("/login", response_model=SystemAuthResponse)
async def login(
    payload: SystemLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
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

    result = await db.execute(select(SystemUser).order_by(SystemUser.id))
    users = result.scalars().all()
    return AdminUserListResponse(
        users=[await _admin_user_response(db, user) for user in users]
    )


@router.put("/admin/users/{user_id}/status", response_model=AdminUserResponse)
async def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    admin = await _get_current_admin_user(request, db)
    next_status = payload.status.strip().lower()
    if next_status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="用户状态只能是 active 或 inactive")
    if admin.id == user_id and next_status != "active":
        raise HTTPException(status_code=400, detail="不能禁用当前管理员账号")

    result = await db.execute(select(SystemUser).where(SystemUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.status = next_status
    if next_status == "inactive":
        await db.execute(delete(SystemSession).where(SystemSession.user_id == user_id))
    await db.commit()
    await db.refresh(user)
    return await _admin_user_response(db, user)


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
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="不能重置当前管理员账号密码")

    result = await db.execute(select(SystemUser).where(SystemUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    temporary_password = secrets.token_urlsafe(18)
    user.password_hash = hash_password(temporary_password)
    user.status = "active"
    await db.execute(delete(SystemSession).where(SystemSession.user_id == user_id))
    await db.commit()
    await db.refresh(user)
    return AdminPasswordResetResponse(
        user=await _admin_user_response(db, user),
        temporary_password=temporary_password,
    )


# ── Google OAuth ──────────────────────────────────────────────


@router.get("/email/config")
async def email_config_status() -> dict[str, bool]:
    smtp_configured = bool(settings.smtp_user and settings.smtp_password)
    return {
        "debug": bool(settings.debug),
        "smtp_configured": smtp_configured,
        "email_login_available": bool(settings.debug or smtp_configured),
    }


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "openid email profile"
WECHAT_AUTH_URL = "https://open.weixin.qq.com/connect/qrconnect"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"
QQ_AUTH_URL = "https://graph.qq.com/oauth2.0/authorize"
QQ_TOKEN_URL = "https://graph.qq.com/oauth2.0/token"
QQ_ME_URL = "https://graph.qq.com/oauth2.0/me"
QQ_USERINFO_URL = "https://graph.qq.com/user/get_user_info"
_OAUTH_STATE_TTL = 600  # 10 分钟
OAUTH_STATE_COOKIE_NAME = "oauth_state_nonce"


def _frontend_origin_is_allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse((url or "").strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not parsed.hostname
    ):
        return False

    host = parsed.hostname.lower()
    if host == "localhost":
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return ip.is_loopback or ip.is_private


def _normalize_frontend_origin(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urllib.parse.urlparse(url.strip())
    origin = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    if not _frontend_origin_is_allowed(origin):
        return None
    return origin


def _frontend_url_from_request(request: Request) -> str:
    for header in ("origin", "referer"):
        origin = _normalize_frontend_origin(request.headers.get(header))
        if origin:
            return origin
    return "http://localhost:3000"


def _frontend_url_from_state(frontend_url: str | None) -> str:
    return _normalize_frontend_origin(frontend_url) or "http://localhost:3000"


def _oauth_signing_key() -> bytes:
    import hashlib

    configured_key = os.getenv("APP_ENCRYPTION_KEY", "").strip()
    if configured_key:
        material = configured_key
    else:
        secrets_material = [
            settings.google_client_secret,
            settings.wechat_client_secret,
            settings.qq_client_secret,
        ]
        material = "|".join(item.strip() for item in secrets_material if item.strip())
    if not material:
        raise RuntimeError(
            "OAuth state signing requires APP_ENCRYPTION_KEY or an OAuth client secret"
        )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _make_oauth_state(
    frontend_url: str | None = None,
    redirect_uri: str | None = None,
    nonce: str | None = None,
) -> str:
    """Create a signed OAuth state with the frontend and callback origins."""
    import base64
    import hashlib
    import hmac
    import json

    payload = {
        "exp": int(time.time()) + _OAUTH_STATE_TTL,
        "rnd": secrets.token_hex(8),
    }
    if nonce:
        payload["nonce"] = nonce
    safe_frontend_url = _frontend_url_from_state(frontend_url)
    if safe_frontend_url:
        payload["frontend_url"] = safe_frontend_url
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    sig = hmac.new(
        _oauth_signing_key(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"{payload_b64}.{sig}"


def _decode_oauth_state(state: str) -> dict | None:
    """Validate and decode a signed OAuth state."""
    import base64
    import hashlib
    import hmac
    import json
    from loguru import logger

    try:
        payload_b64, sig = state.rsplit(".", 1)
        expected = hmac.new(
            _oauth_signing_key(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            logger.warning("OAuth state signature mismatch")
            return None

        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if time.time() > int(data["exp"]):
            logger.warning(
                f"OAuth state expired: exp={data['exp']}, now={int(time.time())}"
            )
            return None
        return data
    except Exception as e:
        logger.warning(f"OAuth state parse failed: {type(e).__name__}: {e}")
        return None


def _verify_oauth_state(state: str) -> bool:
    """Validate OAuth state signature and expiry."""
    return _decode_oauth_state(state) is not None


def _new_oauth_state_nonce() -> str:
    return secrets.token_urlsafe(24)


def _set_oauth_state_cookie(response: Response, nonce: str) -> None:
    secure = (
        bool(settings.session_cookie_secure)
        if settings.session_cookie_secure is not None
        else not settings.debug
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=nonce,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=_OAUTH_STATE_TTL,
        path="/system-auth",
    )


def _clear_oauth_state_cookie(response: Response) -> None:
    secure = (
        bool(settings.session_cookie_secure)
        if settings.session_cookie_secure is not None
        else not settings.debug
    )
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        path="/system-auth",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def _oauth_state_nonce_is_valid(request: Request, state_data: dict) -> bool:
    nonce = str(state_data.get("nonce") or "")
    cookie_nonce = request.cookies.get(OAUTH_STATE_COOKIE_NAME, "")
    return bool(nonce) and secrets.compare_digest(nonce, cookie_nonce)


def _oauth_user_email(provider: str, external_id: str, email: str | None = None) -> str:
    normalized_email = (email or "").strip().lower()
    if normalized_email:
        return normalized_email
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in external_id.lower()).strip(
        "_"
    )
    return f"{provider}_{safe_id or secrets.token_hex(8)}@oauth.local"


async def _upsert_oauth_user(
    db: AsyncSession,
    provider: str,
    external_id: str,
    display_name: str,
    avatar_url: str | None = None,
    email: str | None = None,
) -> SystemUser:
    user_email = _oauth_user_email(provider, external_id, email)
    result = await db.execute(select(SystemUser).where(SystemUser.email == user_email))
    user = result.scalar_one_or_none()

    if user is None:
        name = (display_name or provider.title()).strip()[:100] or provider.title()
        user = SystemUser(
            email=user_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            display_name=name,
            avatar_url=avatar_url or None,
            status="active",
        )
        db.add(user)
        await db.flush()
        workspace = Workspace(name=f"{name} 的个人空间", owner_user_id=user.id)
        db.add(workspace)
        await db.flush()
        db.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        )
    else:
        if display_name and user.display_name.startswith(provider.title()):
            user.display_name = display_name[:100]
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url

    return user


async def _redirect_with_oauth_session(
    db: AsyncSession, user: SystemUser, frontend_url: str | None
) -> RedirectResponse:
    token = create_session_token()
    db.add(
        SystemSession(
            user_id=user.id,
            session_token_hash=hash_token(token),
            expires_at=session_expires_at().replace(tzinfo=None),
        )
    )
    await db.commit()
    redirect = RedirectResponse(_frontend_url_from_state(frontend_url))
    set_session_cookie(redirect, token)
    _clear_oauth_state_cookie(redirect)
    return redirect


def _google_redirect_uri() -> str:
    configured = (settings.google_redirect_uri or "").strip()
    return (
        configured
        or f"http://localhost:{settings.app_port}/system-auth/google/callback"
    )


def _wechat_redirect_uri() -> str:
    return (settings.wechat_redirect_uri or "").strip()


def _qq_redirect_uri() -> str:
    return (settings.qq_redirect_uri or "").strip()


@router.get("/wechat/login")
async def wechat_login(request: Request, frontend_url: str = ""):
    if (
        not settings.wechat_client_id
        or not settings.wechat_client_secret
        or not _wechat_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="WeChat login is not configured")

    redirect_uri = _wechat_redirect_uri()
    nonce = _new_oauth_state_nonce()
    state = _make_oauth_state(
        _normalize_frontend_origin(frontend_url) or _frontend_url_from_request(request),
        redirect_uri,
        nonce=nonce,
    )
    params = {
        "appid": settings.wechat_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    url = f"{WECHAT_AUTH_URL}?{urllib.parse.urlencode(params)}#wechat_redirect"
    redirect = RedirectResponse(url)
    _set_oauth_state_cookie(redirect, nonce)
    return redirect


@router.get("/qq/login")
async def qq_login(request: Request, frontend_url: str = ""):
    if (
        not settings.qq_client_id
        or not settings.qq_client_secret
        or not _qq_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="QQ login is not configured")

    redirect_uri = _qq_redirect_uri()
    nonce = _new_oauth_state_nonce()
    state = _make_oauth_state(
        _normalize_frontend_origin(frontend_url) or _frontend_url_from_request(request),
        redirect_uri,
        nonce=nonce,
    )
    params = {
        "client_id": settings.qq_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "get_user_info",
        "state": state,
    }
    url = f"{QQ_AUTH_URL}?{urllib.parse.urlencode(params)}"
    redirect = RedirectResponse(url)
    _set_oauth_state_cookie(redirect, nonce)
    return redirect


async def _validate_oauth_callback_state(request: Request, state: str) -> dict:
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")
    state_data = _decode_oauth_state(state)
    if state_data is None or not _oauth_state_nonce_is_valid(request, state_data):
        raise HTTPException(
            status_code=400, detail="Invalid OAuth state, please sign in again"
        )
    return state_data


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
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=15.0),
            proxy=settings.http_proxy.strip() or None,
        ) as client:
            token_resp = await client.get(
                WECHAT_TOKEN_URL,
                params={
                    "appid": settings.wechat_client_id,
                    "secret": settings.wechat_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            openid = token_data.get("openid")
            if token_resp.status_code != 200 or not access_token or not openid:
                raise HTTPException(
                    status_code=400, detail="WeChat token exchange failed"
                )

            user_resp = await client.get(
                WECHAT_USERINFO_URL,
                params={
                    "access_token": access_token,
                    "openid": openid,
                    "lang": "zh_CN",
                },
            )
            user_info = user_resp.json()
            if user_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="WeChat user info failed")
    except httpx.HTTPError as e:
        logger.error(f"WeChat OAuth network request failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502, detail=f"Cannot connect to WeChat service: {e}"
        )
    except HTTPException:
        raise

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
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=15.0),
            proxy=settings.http_proxy.strip() or None,
        ) as client:
            token_resp = await client.get(
                QQ_TOKEN_URL,
                params={
                    "grant_type": "authorization_code",
                    "client_id": settings.qq_client_id,
                    "client_secret": settings.qq_client_secret,
                    "code": code,
                    "redirect_uri": state_data.get("redirect_uri")
                    or _qq_redirect_uri(),
                    "fmt": "json",
                },
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if token_resp.status_code != 200 or not access_token:
                raise HTTPException(status_code=400, detail="QQ token exchange failed")

            me_resp = await client.get(
                QQ_ME_URL, params={"access_token": access_token, "fmt": "json"}
            )
            me_data = me_resp.json()
            openid = me_data.get("openid")
            if me_resp.status_code != 200 or not openid:
                raise HTTPException(status_code=400, detail="QQ openid fetch failed")

            user_resp = await client.get(
                QQ_USERINFO_URL,
                params={
                    "access_token": access_token,
                    "oauth_consumer_key": settings.qq_client_id,
                    "openid": openid,
                    "fmt": "json",
                },
            )
            user_info = user_resp.json()
            if user_resp.status_code != 200 or user_info.get("ret", 0) != 0:
                raise HTTPException(status_code=400, detail="QQ user info failed")
    except httpx.HTTPError as e:
        logger.error(f"QQ OAuth network request failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502, detail=f"Cannot connect to QQ service: {e}"
        )
    except HTTPException:
        raise

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
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google 登录未配置")

    redirect_uri = _google_redirect_uri()
    nonce = _new_oauth_state_nonce()
    state = _make_oauth_state(
        _normalize_frontend_origin(frontend_url) or _frontend_url_from_request(request),
        redirect_uri,
        nonce=nonce,
    )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    redirect = RedirectResponse(url)
    _set_oauth_state_cookie(redirect, nonce)
    return redirect


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
    httpx_timeout = httpx.Timeout(30.0, connect=15.0)
    proxy = settings.http_proxy.strip() or None

    # 自动检测 Windows 系统代理（浏览器用的那个）
    if not proxy:
        try:
            from urllib.request import getproxies

            sys_proxy = getproxies().get("https") or getproxies().get("http") or ""
            if sys_proxy and sys_proxy.startswith("http"):
                proxy = sys_proxy
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=httpx_timeout, proxy=proxy) as client:
            # 用 code 换 token
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": state_data.get("redirect_uri")
                    or _google_redirect_uri(),
                },
            )
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Google 令牌交换失败")
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="未能获取 Google 访问令牌")

            # 获取用户信息
            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="获取 Google 用户信息失败")
            user_info = user_resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Google OAuth 网络请求失败: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail=f"无法连接 Google 服务: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Google OAuth httpx 阶段异常: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(e).__name__}: {e}"
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

        # 查找或创建系统用户
        result = await db.execute(select(SystemUser).where(SystemUser.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = SystemUser(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                display_name=name,
                avatar_url=picture or None,
                status="active",
            )
            db.add(user)
            await db.flush()
            workspace = Workspace(name=f"{name} 的个人空间", owner_user_id=user.id)
            db.add(workspace)
            await db.flush()
            db.add(
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=user.id, role="owner"
                )
            )
        elif picture and not user.avatar_url:
            user.avatar_url = picture

        # 创建会话并设置 Cookie
        token = create_session_token()
        db.add(
            SystemSession(
                user_id=user.id,
                session_token_hash=hash_token(token),
                expires_at=session_expires_at().replace(tzinfo=None),
            )
        )
        await db.commit()

        frontend_url = _frontend_url_from_state(state_data.get("frontend_url"))
        redirect = RedirectResponse(frontend_url)
        set_session_cookie(redirect, token)
        _clear_oauth_state_cookie(redirect)
        return redirect
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Google OAuth 回调异常: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(e).__name__}: {e}"
        )
