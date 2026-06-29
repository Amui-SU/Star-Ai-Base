import pytest

from tests.system_auth.helpers import register_user
from tests.system_auth.helpers import send_code


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    code = await send_code(client, "alice@example.com")
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
    code = await send_code(client, "mobile@example.com")
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
async def test_update_display_name(client):
    code = await send_code(client, "renamer@example.com")
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
