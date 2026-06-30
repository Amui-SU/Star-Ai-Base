"""OAuth provider token and userinfo network helpers."""

import httpx
from fastapi import HTTPException

from app.config import settings
from app.services.system_auth_oauth_flow import (
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    QQ_ME_URL,
    QQ_TOKEN_URL,
    QQ_USERINFO_URL,
    WECHAT_TOKEN_URL,
    WECHAT_USERINFO_URL,
    google_redirect_uri,
    qq_redirect_uri,
)


def oauth_system_proxy_url() -> str | None:
    configured_proxy = (settings.http_proxy or "").strip()
    if configured_proxy:
        return configured_proxy

    try:
        from urllib.request import getproxies

        system_proxy = getproxies().get("https") or getproxies().get("http") or ""
        if system_proxy and system_proxy.startswith("http"):
            return system_proxy
    except Exception:
        return None
    return None


async def fetch_wechat_oauth_user(
    code: str,
    *,
    async_client_factory=httpx.AsyncClient,
) -> dict:
    async with async_client_factory(
        timeout=httpx.Timeout(30.0, connect=15.0),
        proxy=(settings.http_proxy or "").strip() or None,
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
            raise HTTPException(status_code=400, detail="WeChat token exchange failed")

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

    return {"openid": openid, "user_info": user_info}


async def fetch_qq_oauth_user(
    code: str,
    state_data: dict,
    *,
    async_client_factory=httpx.AsyncClient,
) -> dict:
    async with async_client_factory(
        timeout=httpx.Timeout(30.0, connect=15.0),
        proxy=(settings.http_proxy or "").strip() or None,
    ) as client:
        token_resp = await client.get(
            QQ_TOKEN_URL,
            params={
                "grant_type": "authorization_code",
                "client_id": settings.qq_client_id,
                "client_secret": settings.qq_client_secret,
                "code": code,
                "redirect_uri": state_data.get("redirect_uri") or qq_redirect_uri(),
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

    return {"openid": openid, "user_info": user_info}


async def fetch_google_oauth_user(
    code: str,
    state_data: dict,
    *,
    async_client_factory=httpx.AsyncClient,
) -> dict:
    async with async_client_factory(
        timeout=httpx.Timeout(30.0, connect=15.0),
        proxy=oauth_system_proxy_url(),
    ) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": state_data.get("redirect_uri") or google_redirect_uri(),
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google 令牌交换失败")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="未能获取 Google 访问令牌")

        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="获取 Google 用户信息失败")
        return user_resp.json()
