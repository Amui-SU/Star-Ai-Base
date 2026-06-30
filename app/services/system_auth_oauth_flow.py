"""OAuth login and account flow helpers for system authentication."""

import secrets
import urllib.parse

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import SystemSession, SystemUser, Workspace, WorkspaceMember
from app.security import (
    create_session_token,
    hash_password,
    hash_token,
    session_expires_at,
    set_session_cookie,
)
from app.services.system_auth_oauth import (
    clear_oauth_state_cookie,
    decode_oauth_state,
    frontend_url_from_request,
    frontend_url_from_state,
    make_oauth_state,
    new_oauth_state_nonce,
    normalize_frontend_origin,
    oauth_state_nonce_is_valid,
    oauth_user_email,
    set_oauth_state_cookie,
)

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


def google_redirect_uri() -> str:
    configured = (settings.google_redirect_uri or "").strip()
    return (
        configured
        or f"http://localhost:{settings.app_port}/system-auth/google/callback"
    )


def wechat_redirect_uri() -> str:
    return (settings.wechat_redirect_uri or "").strip()


def qq_redirect_uri() -> str:
    return (settings.qq_redirect_uri or "").strip()


def build_wechat_login_redirect(request: Request, frontend_url: str = ""):
    if (
        not settings.wechat_client_id
        or not settings.wechat_client_secret
        or not wechat_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="WeChat login is not configured")

    redirect_uri = wechat_redirect_uri()
    nonce = new_oauth_state_nonce()
    state = make_oauth_state(
        normalize_frontend_origin(frontend_url) or frontend_url_from_request(request),
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
    set_oauth_state_cookie(redirect, nonce)
    return redirect


def build_qq_login_redirect(request: Request, frontend_url: str = ""):
    if (
        not settings.qq_client_id
        or not settings.qq_client_secret
        or not qq_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="QQ login is not configured")

    redirect_uri = qq_redirect_uri()
    nonce = new_oauth_state_nonce()
    state = make_oauth_state(
        normalize_frontend_origin(frontend_url) or frontend_url_from_request(request),
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
    redirect = RedirectResponse(f"{QQ_AUTH_URL}?{urllib.parse.urlencode(params)}")
    set_oauth_state_cookie(redirect, nonce)
    return redirect


def build_google_login_redirect(request: Request, frontend_url: str = ""):
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google 登录未配置")

    redirect_uri = google_redirect_uri()
    nonce = new_oauth_state_nonce()
    state = make_oauth_state(
        normalize_frontend_origin(frontend_url) or frontend_url_from_request(request),
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
    redirect = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}")
    set_oauth_state_cookie(redirect, nonce)
    return redirect


async def validate_oauth_callback_state(request: Request, state: str) -> dict:
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")
    state_data = decode_oauth_state(state)
    if state_data is None or not oauth_state_nonce_is_valid(request, state_data):
        raise HTTPException(
            status_code=400, detail="Invalid OAuth state, please sign in again"
        )
    return state_data


async def upsert_oauth_user(
    db: AsyncSession,
    provider: str,
    external_id: str,
    display_name: str,
    avatar_url: str | None = None,
    email: str | None = None,
    update_default_display_name: bool = True,
) -> SystemUser:
    user_email = oauth_user_email(provider, external_id, email)
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
        if (
            update_default_display_name
            and display_name
            and user.display_name.startswith(provider.title())
        ):
            user.display_name = display_name[:100]
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url

    return user


async def redirect_with_oauth_session(
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
    redirect = RedirectResponse(frontend_url_from_state(frontend_url))
    set_session_cookie(redirect, token)
    clear_oauth_state_cookie(redirect)
    return redirect
