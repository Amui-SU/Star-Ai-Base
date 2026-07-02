"""Request-level runtime helpers for system authentication callbacks."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


def email_config_status(
    *,
    debug: bool,
    smtp_user: str | None,
    smtp_password: str | None,
) -> dict[str, bool]:
    smtp_configured = bool(smtp_user and smtp_password)
    return {
        "debug": bool(debug),
        "smtp_configured": smtp_configured,
        "email_login_available": bool(debug or smtp_configured),
    }


def oauth_network_error(
    provider: str,
    exc: httpx.HTTPError,
    *,
    logger: Any,
) -> HTTPException:
    logger.error(f"{provider} OAuth network request failed: {type(exc).__name__}")
    return HTTPException(
        status_code=502,
        detail=f"Cannot connect to {provider} OAuth service",
    )


async def handle_wechat_oauth_callback(
    *,
    request: Any,
    code: str,
    error: str,
    state: str,
    db: AsyncSession,
    settings: Any,
    async_client_factory: Any,
    validate_oauth_callback_state: Callable[[Any, str], Awaitable[dict[str, Any]]],
    fetch_wechat_oauth_user: Callable[..., Awaitable[dict[str, Any]]],
    upsert_oauth_user: Callable[..., Awaitable[Any]],
    redirect_with_oauth_session: Callable[..., Awaitable[Any]],
    wechat_redirect_uri: Callable[[], str],
    logger: Any,
) -> Any:
    if error:
        raise HTTPException(
            status_code=400, detail=f"WeChat authorization failed: {error}"
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if (
        not settings.wechat_client_id
        or not settings.wechat_client_secret
        or not wechat_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="WeChat login is not configured")
    state_data = await validate_oauth_callback_state(request, state)

    try:
        oauth_user = await fetch_wechat_oauth_user(
            code, async_client_factory=async_client_factory
        )
    except httpx.HTTPError as exc:
        raise oauth_network_error("WeChat", exc, logger=logger) from exc
    except HTTPException:
        raise

    openid = oauth_user["openid"]
    user_info = oauth_user["user_info"]
    external_id = user_info.get("openid") or openid
    user = await upsert_oauth_user(
        db,
        "wechat",
        external_id,
        user_info.get("nickname") or "WeChat User",
        user_info.get("headimgurl") or None,
    )
    return await redirect_with_oauth_session(
        db,
        user,
        state_data.get("frontend_url"),
    )


async def handle_qq_oauth_callback(
    *,
    request: Any,
    code: str,
    error: str,
    state: str,
    db: AsyncSession,
    settings: Any,
    async_client_factory: Any,
    validate_oauth_callback_state: Callable[[Any, str], Awaitable[dict[str, Any]]],
    fetch_qq_oauth_user: Callable[..., Awaitable[dict[str, Any]]],
    upsert_oauth_user: Callable[..., Awaitable[Any]],
    redirect_with_oauth_session: Callable[..., Awaitable[Any]],
    qq_redirect_uri: Callable[[], str],
    logger: Any,
) -> Any:
    if error:
        raise HTTPException(status_code=400, detail=f"QQ authorization failed: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if (
        not settings.qq_client_id
        or not settings.qq_client_secret
        or not qq_redirect_uri()
    ):
        raise HTTPException(status_code=501, detail="QQ login is not configured")
    state_data = await validate_oauth_callback_state(request, state)

    try:
        oauth_user = await fetch_qq_oauth_user(
            code,
            state_data,
            async_client_factory=async_client_factory,
        )
    except httpx.HTTPError as exc:
        raise oauth_network_error("QQ", exc, logger=logger) from exc
    except HTTPException:
        raise

    openid = oauth_user["openid"]
    user_info = oauth_user["user_info"]
    user = await upsert_oauth_user(
        db,
        "qq",
        openid,
        user_info.get("nickname") or "QQ User",
        user_info.get("figureurl_qq_2") or user_info.get("figureurl_qq_1") or None,
    )
    return await redirect_with_oauth_session(
        db,
        user,
        state_data.get("frontend_url"),
    )


async def handle_google_oauth_callback(
    *,
    request: Any,
    code: str,
    error: str,
    state: str,
    db: AsyncSession,
    settings: Any,
    async_client_factory: Any,
    validate_oauth_callback_state: Callable[[Any, str], Awaitable[dict[str, Any]]],
    fetch_google_oauth_user: Callable[..., Awaitable[dict[str, Any]]],
    upsert_oauth_user: Callable[..., Awaitable[Any]],
    redirect_with_oauth_session: Callable[..., Awaitable[Any]],
    logger: Any,
) -> Any:
    if error:
        raise HTTPException(status_code=400, detail=f"Google 授权失败: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="缺少授权码")
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=501, detail="Google 登录未配置")

    state_data = await validate_oauth_callback_state(request, state)

    try:
        user_info = await fetch_google_oauth_user(
            code,
            state_data,
            async_client_factory=async_client_factory,
        )
    except httpx.HTTPError as exc:
        raise oauth_network_error("Google", exc, logger=logger) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Google OAuth httpx 阶段异常: {type(exc).__name__}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(exc).__name__}"
        ) from exc

    try:
        if not user_info.get("verified_email", False):
            raise HTTPException(status_code=400, detail="Google 邮箱未验证，无法注册")

        email = (user_info.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Google 账号未返回邮箱")

        name = user_info.get("name") or email.split("@")[0]
        picture = user_info.get("picture") or ""

        user = await upsert_oauth_user(
            db,
            "google",
            email,
            name,
            picture or None,
            email=email,
            update_default_display_name=False,
        )
        return await redirect_with_oauth_session(
            db,
            user,
            state_data.get("frontend_url"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Google OAuth 回调异常: {type(exc).__name__}")
        raise HTTPException(
            status_code=500, detail=f"Google 登录异常: {type(exc).__name__}"
        ) from exc
