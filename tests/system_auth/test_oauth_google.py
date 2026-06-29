import urllib.parse

import pytest
from app.config import settings
from app.routers.system_auth import OAUTH_STATE_COOKIE_NAME
from app.routers.system_auth import _decode_oauth_state
from app.routers.system_auth import _make_oauth_state
from app.routers.system_auth import _oauth_signing_key

from tests.system_auth.helpers import has_oauth_nonce_clear_cookie
from tests.system_auth.helpers import set_oauth_nonce_cookie


def test_oauth_state_preserves_frontend_origin(monkeypatch):
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")

    state = _make_oauth_state("http://192.168.1.199:3000")
    data = _decode_oauth_state(state)

    assert data is not None
    assert data["frontend_url"] == "http://192.168.1.199:3000"


def test_oauth_state_uses_non_google_provider_secret(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(settings, "google_client_secret", "")
    monkeypatch.setattr(settings, "wechat_client_secret", "wechat-secret")
    monkeypatch.setattr(settings, "qq_client_secret", "")

    state = _make_oauth_state("http://localhost:3000")

    assert _decode_oauth_state(state) is not None

    monkeypatch.setattr(settings, "wechat_client_secret", "rotated-secret")

    assert _decode_oauth_state(state) is None


def test_oauth_signing_key_rejects_empty_secret_material(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(settings, "google_client_secret", "")
    monkeypatch.setattr(settings, "wechat_client_secret", "")
    monkeypatch.setattr(settings, "qq_client_secret", "")

    with pytest.raises(RuntimeError, match="OAuth state signing"):
        _oauth_signing_key()


@pytest.mark.asyncio
async def test_google_callback_redirects_to_frontend_origin(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")

    nonce = "google-callback-nonce"
    state = _make_oauth_state("http://192.168.1.199:3000", nonce=nonce)
    set_oauth_nonce_cookie(client, nonce)

    class _FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            return _FakeResponse(200, {"access_token": "token"})

        async def get(self, url, headers=None):
            return _FakeResponse(
                200,
                {
                    "verified_email": True,
                    "email": "phone@example.com",
                    "name": "Phone User",
                    "picture": "https://example.com/avatar.png",
                },
            )

    monkeypatch.setattr("app.routers.system_auth.httpx.AsyncClient", _FakeAsyncClient)

    response = await client.get(
        f"/system-auth/google/callback?code=test-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    assert response.headers["location"] == "http://192.168.1.199:3000"
    assert has_oauth_nonce_clear_cookie(response)
    assert client.cookies.get(OAUTH_STATE_COOKIE_NAME) is None


@pytest.mark.asyncio
async def test_google_login_state_uses_explicit_frontend_url(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")

    response = await client.get(
        "/system-auth/google/login",
        params={"frontend_url": "http://192.168.1.199:3000"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    redirect_url = urllib.parse.urlparse(response.headers["location"])
    query = urllib.parse.parse_qs(redirect_url.query)
    state = query["state"][0]

    data = _decode_oauth_state(state)
    assert data is not None
    assert data["frontend_url"] == "http://192.168.1.199:3000"


@pytest.mark.asyncio
async def test_google_login_sets_oauth_state_nonce_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")

    response = await client.get("/system-auth/google/login", follow_redirects=False)

    assert response.status_code in {302, 307}
    nonce_cookie = response.cookies.get(OAUTH_STATE_COOKIE_NAME)
    assert nonce_cookie
    redirect_url = urllib.parse.urlparse(response.headers["location"])
    state = urllib.parse.parse_qs(redirect_url.query)["state"][0]
    state_data = _decode_oauth_state(state)
    assert state_data is not None
    assert state_data["nonce"] == nonce_cookie


@pytest.mark.asyncio
async def test_google_callback_rejects_missing_oauth_state_nonce_cookie(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    state = _make_oauth_state("http://localhost:3000", nonce="nonce-from-other-client")

    response = await client.get(
        f"/system-auth/google/callback?code=test-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Invalid OAuth state" in response.json()["detail"]


@pytest.mark.asyncio
async def test_google_login_uses_configured_redirect_uri(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(
        settings,
        "google_redirect_uri",
        "http://localhost:8000/system-auth/google/callback",
    )

    response = await client.get(
        "http://192.168.1.199:8000/system-auth/google/login",
        params={"frontend_url": "http://192.168.1.199:3000"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    redirect_url = urllib.parse.urlparse(response.headers["location"])
    query = urllib.parse.parse_qs(redirect_url.query)

    assert (
        query["redirect_uri"][0] == "http://localhost:8000/system-auth/google/callback"
    )
    state_data = _decode_oauth_state(query["state"][0])
    assert state_data is not None
    assert (
        state_data["redirect_uri"]
        == "http://localhost:8000/system-auth/google/callback"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,settings_patch,callback_path,nonce,redirect_uri,secret",
    [
        (
            "wechat",
            {
                "wechat_client_id": "wechat-id",
                "wechat_client_secret": "wechat-secret",
                "wechat_redirect_uri": "https://example.com/system-auth/wechat/callback",
            },
            "/system-auth/wechat/callback",
            "wechat-network-nonce",
            "https://example.com/system-auth/wechat/callback",
            "wechat-secret",
        ),
        (
            "qq",
            {
                "qq_client_id": "qq-id",
                "qq_client_secret": "qq-secret",
                "qq_redirect_uri": "https://example.com/system-auth/qq/callback",
            },
            "/system-auth/qq/callback",
            "qq-network-nonce",
            "https://example.com/system-auth/qq/callback",
            "qq-secret",
        ),
        (
            "google",
            {
                "google_client_id": "google-id",
                "google_client_secret": "google-secret",
                "google_redirect_uri": "https://example.com/system-auth/google/callback",
            },
            "/system-auth/google/callback",
            "google-network-nonce",
            "https://example.com/system-auth/google/callback",
            "google-secret",
        ),
    ],
)
async def test_oauth_network_errors_do_not_echo_client_secret(
    client,
    monkeypatch,
    provider,
    settings_patch,
    callback_path,
    nonce,
    redirect_uri,
    secret,
):
    import httpx
    import app.routers.system_auth as system_auth_router

    for key, value in settings_patch.items():
        monkeypatch.setattr(settings, key, value)
    state = _make_oauth_state("http://localhost:3000", redirect_uri, nonce=nonce)
    set_oauth_nonce_cookie(client, nonce)
    errors = []

    class _FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError(f"connect failed with secret={secret}")

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError(f"connect failed with secret={secret}")

    monkeypatch.setattr(system_auth_router.httpx, "AsyncClient", _FailingAsyncClient)
    if hasattr(system_auth_router, "logger"):
        monkeypatch.setattr(
            system_auth_router.logger,
            "error",
            lambda message, *args: errors.append((message, args)),
        )

    response = await client.get(
        f"{callback_path}?code=test-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert secret not in response.text
    assert errors
    assert all(secret not in message for message, _args in errors)
    assert all(secret not in [str(arg) for arg in args] for _message, args in errors)
