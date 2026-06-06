import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    register_response = await client.post(
        "/system-auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
            "display_name": "Alice",
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
