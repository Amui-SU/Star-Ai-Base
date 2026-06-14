import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

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
    SystemAuthResponse,
    SystemDisplayNameUpdateRequest,
    SystemLoginRequest,
    SystemRegisterRequest,
    SystemSession,
    SystemUser,
    SystemUserResponse,
    VerificationCode,
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

router = APIRouter(prefix="/system-auth", tags=["系统认证"])

MAX_BCRYPT_PASSWORD_BYTES = 72
_EMAIL_RE = __import__("re").compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
_CODE_TTL_SECONDS = 300  # 5 分钟有效
_MAX_ATTEMPTS = 5  # 验证码最多错误尝试次数

# IP 级别频率限制（内存）
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


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class SendCodeRequest(BaseModel):
    email: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES


def _duplicate_email_exception() -> HTTPException:
    return HTTPException(status_code=400, detail="邮箱已注册")


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(status_code=401, detail="邮箱或密码错误")


def _user_response(user: SystemUser) -> SystemUserResponse:
    return SystemUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
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
) -> None:
    token = create_session_token()
    db.add(
        SystemSession(
            user_id=user_id,
            session_token_hash=hash_token(token),
            expires_at=session_expires_at().replace(tzinfo=None),
        )
    )
    set_session_cookie(response, token)


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
    token = request.cookies.get(SESSION_COOKIE_NAME)
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

    if _as_aware_utc(session.expires_at) <= _utc_now():
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    user_result = await db.execute(
        select(SystemUser).where(SystemUser.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    session.last_seen_at = _naive_utc_now()
    await db.commit()
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
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    # 清理过期验证码
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
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
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
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
        await _create_system_session(db, user.id, response)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _duplicate_email_exception() from None

    return SystemAuthResponse(
        user=_user_response(user),
        workspace=_workspace_response(workspace, member),
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
    await _create_system_session(db, user.id, response)
    await db.commit()

    return SystemAuthResponse(
        user=_user_response(user),
        workspace=_workspace_response(workspace, member),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        result = await db.execute(
            select(SystemSession).where(
                SystemSession.session_token_hash == hash_token(token)
            )
        )
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = _naive_utc_now()
            await db.commit()

    clear_session_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=SystemUserResponse)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    user = await _get_current_user(request, db)
    return _user_response(user)


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
    return _user_response(user)


# ── Google OAuth ──────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "openid email profile"
_OAUTH_STATE_TTL = 600  # 10 分钟


def _make_oauth_state() -> str:
    """生成 HMAC 签名的 OAuth state（URL-safe，不依赖 Fernet/APP_ENCRYPTION_KEY）。"""
    import base64
    import hashlib
    import hmac
    import json

    payload = json.dumps(
        {"exp": int(time.time()) + _OAUTH_STATE_TTL, "rnd": secrets.token_hex(8)}
    )
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    key = hashlib.sha256(
        settings.google_client_secret.encode()
        if settings.google_client_secret
        else b"dev"
    ).digest()
    sig = hmac.new(key, payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload_b64}.{sig}"


def _verify_oauth_state(state: str) -> bool:
    """验证 OAuth state 签名和有效期。"""
    import base64
    import hashlib
    import hmac
    import json
    from loguru import logger

    try:
        payload_b64, sig = state.rsplit(".", 1)
        key = hashlib.sha256(
            settings.google_client_secret.encode()
            if settings.google_client_secret
            else b"dev"
        ).digest()
        expected = hmac.new(key, payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            logger.warning("OAuth state 签名不匹配")
            return False
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        ok = time.time() <= data["exp"]
        if not ok:
            logger.warning(
                f"OAuth state 已过期: exp={data['exp']}, now={int(time.time())}"
            )
        return ok
    except Exception as e:
        logger.warning(f"OAuth state 解析失败: {type(e).__name__}: {e}")
        return False


def _google_redirect_uri() -> str:
    if settings.google_redirect_uri:
        return settings.google_redirect_uri
    return f"http://localhost:{settings.app_port}/system-auth/google/callback"


@router.get("/google/login")
async def google_login(request: Request):
    """重定向到 Google OAuth 授权页面。"""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google 登录未配置")

    state = _make_oauth_state()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(
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
    if not state:
        raise HTTPException(status_code=400, detail="缺少 OAuth state 参数")
    if not _verify_oauth_state(state):
        raise HTTPException(status_code=400, detail="无效的 OAuth state，请重新登录")

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
                    "redirect_uri": _google_redirect_uri(),
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
        import traceback

        traceback.print_exc()
        logger.error(f"Google OAuth httpx 阶段异常: {type(e).__name__}: {e}")
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

        frontend_url = "http://localhost:3000"
        redirect = RedirectResponse(frontend_url)
        set_session_cookie(redirect, token)
        return redirect
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Google OAuth 回调异常: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(e).__name__}: {e}"
        )
