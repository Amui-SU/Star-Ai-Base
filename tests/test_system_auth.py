import urllib.parse

import pytest
from app.config import settings
from app.routers.system_auth import _IP_RATE_MAX, _MAX_ATTEMPTS
from app.routers.system_auth import OAUTH_STATE_COOKIE_NAME
from app.routers.system_auth import _decode_oauth_state
from app.routers.system_auth import _make_oauth_state
from app.routers.system_auth import _oauth_signing_key


def _set_oauth_nonce_cookie(client, nonce: str) -> None:
    client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        nonce,
        domain="testserver.local",
        path="/system-auth",
    )


def _has_oauth_nonce_clear_cookie(response) -> bool:
    return any(
        cookie.startswith(f"{OAUTH_STATE_COOKIE_NAME}=") and "Max-Age=0" in cookie
        for cookie in response.headers.get_list("set-cookie")
    )


async def _send_code(client, email: str) -> str | None:
    """发送验证码，返回 code（DEBUG 模式）或 None"""
    resp = await client.post("/system-auth/send-code", json={"email": email})
    if resp.status_code != 200:
        return None
    return resp.json().get("code")


async def _register_user(
    client,
    email: str,
    *,
    password: str = "correct horse battery staple",
    display_name: str = "Test User",
) -> dict:
    code = await _send_code(client, email)
    assert code is not None
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    code = await _send_code(client, "alice@example.com")
    assert code is not None

    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
            "display_name": "Alice",
            "code": code,
        },
    )
    assert register_response.status_code == 200
    body = register_response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["workspace"]["name"] == "Alice 的个人空间"
    assert "system_session" in register_response.cookies

    me_response = await client.get("/system-auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "alice@example.com"

    logout_response = await client.post("/system-auth/logout")
    assert logout_response.status_code == 200

    after_logout_response = await client.get("/system-auth/me")
    assert after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_mobile_bearer_session_can_access_protected_endpoints(client):
    code = await _send_code(client, "mobile@example.com")
    assert code is not None

    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "mobile@example.com",
            "password": "correct horse battery staple",
            "display_name": "Mobile User",
            "code": code,
        },
    )
    assert register_response.status_code == 200
    token = register_response.json().get("session_token")
    assert token

    client.cookies.clear()

    me_response = await client.get(
        "/system-auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "mobile@example.com"


@pytest.mark.asyncio
async def test_first_registered_user_can_manage_users(client):
    admin = await _register_user(client, "admin@example.com", display_name="Admin User")
    user = await _register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.get(
        "/system-auth/admin/users",
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert response.status_code == 200
    users = response.json()["users"]
    assert [item["email"] for item in users] == [
        "admin@example.com",
        "member@example.com",
    ]
    assert users[0]["is_admin"] is True
    assert users[1]["is_admin"] is False
    assert user["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_regular_user_cannot_manage_users(client):
    await _register_user(client, "admin@example.com", display_name="Admin User")
    member = await _register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.get(
        "/system-auth/admin/users",
        headers={"Authorization": f"Bearer {member['session_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_disable_and_enable_regular_user(client):
    admin = await _register_user(client, "admin@example.com", display_name="Admin User")
    member = await _register_user(
        client,
        "member@example.com",
        password="member-password",
        display_name="Member",
    )
    client.cookies.clear()

    disable_response = await client.put(
        f"/system-auth/admin/users/{member['user']['id']}/status",
        json={"status": "inactive"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "inactive"

    login_while_disabled = await client.post(
        "/system-auth/login",
        json={"email": "member@example.com", "password": "member-password"},
    )
    assert login_while_disabled.status_code == 401

    enable_response = await client.put(
        f"/system-auth/admin/users/{member['user']['id']}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert enable_response.status_code == 200
    assert enable_response.json()["status"] == "active"

    login_after_enable = await client.post(
        "/system-auth/login",
        json={"email": "member@example.com", "password": "member-password"},
    )
    assert login_after_enable.status_code == 200


@pytest.mark.asyncio
async def test_disabling_user_revokes_existing_sessions(client):
    admin = await _register_user(client, "admin@example.com", display_name="Admin User")
    member = await _register_user(
        client,
        "member@example.com",
        password="member-password",
        display_name="Member",
    )
    member_token = member["session_token"]
    client.cookies.clear()

    before_disable = await client.get(
        "/system-auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert before_disable.status_code == 200

    disable_response = await client.put(
        f"/system-auth/admin/users/{member['user']['id']}/status",
        json={"status": "inactive"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )
    assert disable_response.status_code == 200

    enable_response = await client.put(
        f"/system-auth/admin/users/{member['user']['id']}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )
    assert enable_response.status_code == 200

    old_session = await client.get(
        "/system-auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert old_session.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(client):
    admin = await _register_user(client, "admin@example.com", display_name="Admin User")
    client.cookies.clear()

    response = await client.put(
        f"/system-auth/admin/users/{admin['user']['id']}/status",
        json={"status": "inactive"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_reset_regular_user_password(client):
    admin = await _register_user(client, "admin@example.com", display_name="Admin User")
    member = await _register_user(
        client,
        "member@example.com",
        password="old-member-password",
        display_name="Member",
    )
    client.cookies.clear()

    reset_response = await client.post(
        f"/system-auth/admin/users/{member['user']['id']}/reset-password",
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert reset_response.status_code == 200
    temporary_password = reset_response.json()["temporary_password"]
    assert len(temporary_password) >= 16

    old_login = await client.post(
        "/system-auth/login",
        json={"email": "member@example.com", "password": "old-member-password"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/system-auth/login",
        json={"email": "member@example.com", "password": temporary_password},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_update_display_name(client):
    code = await _send_code(client, "renamer@example.com")
    assert code is not None

    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "renamer@example.com",
            "password": "correct horse battery staple",
            "display_name": "Old Name",
            "code": code,
        },
    )
    assert register_response.status_code == 200

    update_response = await client.put(
        "/system-auth/me/display-name",
        json={"display_name": "New Name"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "New Name"

    me_response = await client.get("/system-auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(client):
    response = await client.post(
        "/system-auth/register",
        json={
            "email": "notanemail",
            "password": "correct horse battery staple",
            "display_name": "Bob",
            "code": "000000",
        },
    )
    assert response.status_code == 400
    assert "邮箱格式" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_email(client):
    response = await client.post(
        "/system-auth/login",
        json={"email": "bad@@email..com", "password": "anything"},
    )
    assert response.status_code == 400
    assert "邮箱格式" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_rejects_wrong_code(client):
    code = await _send_code(client, "bob@example.com")
    assert code is not None

    response = await client.post(
        "/system-auth/register",
        json={
            "email": "bob@example.com",
            "password": "secret123456",
            "display_name": "Bob",
            "code": "000000",  # wrong code
        },
    )
    assert response.status_code == 400
    assert "验证码" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_rejects_missing_code(client):
    response = await client.post(
        "/system-auth/register",
        json={
            "email": "carol@example.com",
            "password": "secret123456",
            "display_name": "Carol",
            "code": "123456",  # never sent
        },
    )
    assert response.status_code == 400
    assert "验证码" in response.json()["detail"]


@pytest.mark.asyncio
async def test_send_code_rejects_invalid_email(client):
    response = await client.post("/system-auth/send-code", json={"email": "bademail"})
    assert response.status_code == 400
    assert "邮箱格式" in response.json()["detail"]


@pytest.mark.asyncio
async def test_code_cannot_be_reused(client):
    code = await _send_code(client, "dave@example.com")
    assert code is not None

    # 第一次注册成功
    r1 = await client.post(
        "/system-auth/register",
        json={
            "email": "dave@example.com",
            "password": "secret123456",
            "display_name": "Dave",
            "code": code,
        },
    )
    assert r1.status_code == 200

    # 退出后用同一个验证码再次注册应该失败
    await client.post("/system-auth/logout")
    r2 = await client.post(
        "/system-auth/register",
        json={
            "email": "dave@example.com",
            "password": "otherpass",
            "display_name": "Dave2",
            "code": code,
        },
    )
    assert r2.status_code == 400
    assert "验证码" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_send_code_rate_limit(client):
    """同一 IP 短时间内发送超过限制应返回 429"""
    for i in range(4):
        resp = await client.post(
            "/system-auth/send-code", json={"email": f"ratelimit{i}@example.com"}
        )
        if i < _IP_RATE_MAX:
            assert resp.status_code == 200, f"第{i+1}次应成功"
        else:
            assert resp.status_code == 429, f"第{i+1}次应被限流"
            assert "频繁" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_code_rate_limit_survives_empty_memory_cache(client):
    """IP 限流应持久化，避免多 worker 或进程重启后绕过。"""
    import app.routers.system_auth as system_auth_router

    for i in range(_IP_RATE_MAX):
        resp = await client.post(
            "/system-auth/send-code",
            json={"email": f"persistent-ratelimit{i}@example.com"},
        )
        assert resp.status_code == 200

    system_auth_router._ip_rate_limit.clear()

    resp = await client.post(
        "/system-auth/send-code",
        json={"email": "persistent-ratelimit-blocked@example.com"},
    )

    assert resp.status_code == 429
    assert "频繁" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_code_attempts_limit(client):
    """错误尝试达到上限后验证码失效"""
    code = await _send_code(client, "eve@example.com")
    assert code is not None

    # 前 5 次错误尝试
    for i in range(_MAX_ATTEMPTS):
        resp = await client.post(
            "/system-auth/register",
            json={
                "email": "eve@example.com",
                "password": "secret123456",
                "display_name": "Eve",
                "code": "000000",
            },
        )
        assert resp.status_code == 400
        assert "验证码错误" in resp.json()["detail"]

    # 第 6 次应提示已被锁定（即使正确验证码也不可用）
    resp = await client.post(
        "/system-auth/register",
        json={
            "email": "eve@example.com",
            "password": "secret123456",
            "display_name": "Eve",
            "code": code,
        },
    )
    assert resp.status_code == 400
    assert "次数过多" in resp.json()["detail"]


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
    _set_oauth_nonce_cookie(client, nonce)

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
    assert _has_oauth_nonce_clear_cookie(response)
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
    _set_oauth_nonce_cookie(client, nonce)
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


@pytest.mark.asyncio
async def test_email_config_status_reports_debug_and_smtp(client, monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")

    response = await client.get("/system-auth/email/config")

    assert response.status_code == 200
    assert response.json() == {
        "debug": True,
        "smtp_configured": False,
        "email_login_available": True,
    }


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
    _set_oauth_nonce_cookie(client, nonce)

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
    assert _has_oauth_nonce_clear_cookie(response)
    assert client.cookies.get(OAUTH_STATE_COOKIE_NAME) is None
