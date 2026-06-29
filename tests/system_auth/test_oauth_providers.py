import urllib.parse

import pytest
from app.config import settings
from app.routers.system_auth import OAUTH_STATE_COOKIE_NAME
from app.routers.system_auth import _decode_oauth_state
from app.routers.system_auth import _make_oauth_state

from tests.system_auth.helpers import has_oauth_nonce_clear_cookie
from tests.system_auth.helpers import set_oauth_nonce_cookie


@pytest.mark.asyncio
async def test_wechat_login_requires_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_client_id", "")
    monkeypatch.setattr(settings, "wechat_client_secret", "")
    monkeypatch.setattr(settings, "wechat_redirect_uri", "")

    response = await client.get("/system-auth/wechat/login", follow_redirects=False)

    assert response.status_code == 501


@pytest.mark.asyncio
async def test_wechat_login_redirects_to_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_client_id", "wechat-id")
    monkeypatch.setattr(settings, "wechat_client_secret", "wechat-secret")
    monkeypatch.setattr(
        settings,
        "wechat_redirect_uri",
        "https://example.com/system-auth/wechat/callback",
    )

    response = await client.get(
        "/system-auth/wechat/login",
        params={"frontend_url": "http://localhost:3000"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    redirect_url = urllib.parse.urlparse(response.headers["location"])
    query = urllib.parse.parse_qs(redirect_url.query)
    assert redirect_url.netloc == "open.weixin.qq.com"
    assert query["appid"][0] == "wechat-id"
    assert query["redirect_uri"][0] == "https://example.com/system-auth/wechat/callback"
    state_data = _decode_oauth_state(query["state"][0])
    assert state_data is not None
    assert state_data["frontend_url"] == "http://localhost:3000"
    assert (
        state_data["redirect_uri"] == "https://example.com/system-auth/wechat/callback"
    )
    assert state_data["nonce"] == response.cookies.get(OAUTH_STATE_COOKIE_NAME)


@pytest.mark.asyncio
async def test_qq_login_redirects_to_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "qq_client_id", "qq-id")
    monkeypatch.setattr(settings, "qq_client_secret", "qq-secret")
    monkeypatch.setattr(
        settings,
        "qq_redirect_uri",
        "https://example.com/system-auth/qq/callback",
    )

    response = await client.get(
        "/system-auth/qq/login",
        params={"frontend_url": "http://localhost:3000"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    redirect_url = urllib.parse.urlparse(response.headers["location"])
    query = urllib.parse.parse_qs(redirect_url.query)
    assert redirect_url.netloc == "graph.qq.com"
    assert query["client_id"][0] == "qq-id"
    assert query["redirect_uri"][0] == "https://example.com/system-auth/qq/callback"
    state_data = _decode_oauth_state(query["state"][0])
    assert state_data is not None
    assert state_data["frontend_url"] == "http://localhost:3000"
    assert state_data["nonce"] == response.cookies.get(OAUTH_STATE_COOKIE_NAME)


@pytest.mark.asyncio
async def test_wechat_callback_creates_user_and_redirects(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_client_id", "wechat-id")
    monkeypatch.setattr(settings, "wechat_client_secret", "wechat-secret")
    monkeypatch.setattr(
        settings,
        "wechat_redirect_uri",
        "https://example.com/system-auth/wechat/callback",
    )
    nonce = "wechat-callback-nonce"
    state = _make_oauth_state(
        "http://localhost:3000",
        "https://example.com/system-auth/wechat/callback",
        nonce=nonce,
    )
    set_oauth_nonce_cookie(client, nonce)

    class _FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None, headers=None):
            if "access_token" in url:
                return _FakeResponse(
                    200,
                    {"access_token": "wechat-token", "openid": "wx-openid"},
                )
            return _FakeResponse(
                200,
                {
                    "openid": "wx-openid",
                    "nickname": "Wechat User",
                    "headimgurl": "https://example.com/wx.png",
                },
            )

    monkeypatch.setattr("app.routers.system_auth.httpx.AsyncClient", _FakeAsyncClient)

    response = await client.get(
        f"/system-auth/wechat/callback?code=test-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    assert response.headers["location"] == "http://localhost:3000"
    assert "system_session" in response.cookies
    assert has_oauth_nonce_clear_cookie(response)
    assert client.cookies.get(OAUTH_STATE_COOKIE_NAME) is None
