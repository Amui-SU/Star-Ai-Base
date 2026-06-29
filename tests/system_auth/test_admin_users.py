import pytest

from tests.system_auth.helpers import register_user


@pytest.mark.asyncio
async def test_first_registered_user_can_manage_users(client):
    admin = await register_user(client, "admin@example.com", display_name="Admin User")
    user = await register_user(client, "member@example.com", display_name="Member")
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
    await register_user(client, "admin@example.com", display_name="Admin User")
    member = await register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.get(
        "/system-auth/admin/users",
        headers={"Authorization": f"Bearer {member['session_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_disable_and_enable_regular_user(client):
    admin = await register_user(client, "admin@example.com", display_name="Admin User")
    member = await register_user(
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
    admin = await register_user(client, "admin@example.com", display_name="Admin User")
    member = await register_user(
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
    admin = await register_user(client, "admin@example.com", display_name="Admin User")
    client.cookies.clear()

    response = await client.put(
        f"/system-auth/admin/users/{admin['user']['id']}/status",
        json={"status": "inactive"},
        headers={"Authorization": f"Bearer {admin['session_token']}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_reset_regular_user_password(client):
    admin = await register_user(client, "admin@example.com", display_name="Admin User")
    member = await register_user(
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
