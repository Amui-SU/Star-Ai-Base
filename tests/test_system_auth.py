import pytest
from app.routers.system_auth import _IP_RATE_MAX, _MAX_ATTEMPTS


async def _send_code(client, email: str) -> str | None:
    """发送验证码，返回 code（DEBUG 模式）或 None"""
    resp = await client.post("/system-auth/send-code", json={"email": email})
    if resp.status_code != 200:
        return None
    return resp.json().get("code")


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
