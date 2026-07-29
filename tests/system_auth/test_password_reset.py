from datetime import timedelta

from sqlalchemy import delete, update

import pytest

from app.models import PasswordResetCode, SystemUser, VerificationIpRateLimit
from app.routers.system_auth import _IP_RATE_MAX, _MAX_ATTEMPTS
from app.time_utils import utc_now_naive
from tests.system_auth.helpers import register_user, send_code


async def clear_ip_rate_limit(db_session_factory) -> None:
    async with db_session_factory() as db:
        await db.execute(delete(VerificationIpRateLimit))
        await db.commit()


async def send_reset_code(client, email: str) -> str | None:
    response = await client.post(
        "/system-auth/password-reset/send-code", json={"email": email}
    )
    assert response.status_code == 200
    return response.json().get("code")


@pytest.mark.asyncio
async def test_existing_user_receives_dedicated_reset_code(client, db_session_factory):
    await register_user(client, "reset@example.com")
    await clear_ip_rate_limit(db_session_factory)

    code = await send_reset_code(client, "reset@example.com")

    assert code and len(code) == 6


@pytest.mark.asyncio
async def test_unknown_email_gets_generic_send_response(client):
    response = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "如果该邮箱已注册，重置验证码已发送"
    assert response.json().get("code")


@pytest.mark.asyncio
async def test_reset_send_rejects_invalid_email(client):
    response = await client.post(
        "/system-auth/password-reset/send-code", json={"email": "bad-email"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_send_uses_persisted_ip_rate_limit(client):
    for index in range(_IP_RATE_MAX):
        response = await client.post(
            "/system-auth/password-reset/send-code",
            json={"email": f"missing-{index}@example.com"},
        )
        assert response.status_code == 200

    blocked = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "blocked@example.com"},
    )

    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_reset_send_rejects_a_second_active_code(client, db_session_factory):
    await register_user(client, "duplicate@example.com")
    await clear_ip_rate_limit(db_session_factory)
    assert await send_reset_code(client, "duplicate@example.com")
    await clear_ip_rate_limit(db_session_factory)

    response = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "duplicate@example.com"},
    )

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_confirm_reset_changes_password_consumes_code_and_revokes_sessions(
    client, db_session_factory
):
    registration = await register_user(
        client, "secured@example.com", password="old secure password"
    )
    bearer = registration["session_token"]
    await clear_ip_rate_limit(db_session_factory)
    code = await send_reset_code(client, "secured@example.com")
    assert code

    reset = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "secured@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )

    assert reset.status_code == 200
    assert reset.json() == {"message": "密码已重置，请使用新密码登录"}
    assert (await client.get("/system-auth/me")).status_code == 401
    bearer_me = await client.get(
        "/system-auth/me", headers={"Authorization": f"Bearer {bearer}"}
    )
    assert bearer_me.status_code == 401

    reused = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "secured@example.com",
            "code": code,
            "new_password": "another secure password",
        },
    )
    assert reused.status_code == 400

    old_login = await client.post(
        "/system-auth/login",
        json={
            "email": "secured@example.com",
            "password": "old secure password",
        },
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/system-auth/login",
        json={
            "email": "secured@example.com",
            "password": "new secure password",
        },
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_registration_code_cannot_reset_a_password(client, db_session_factory):
    await register_user(client, "purpose@example.com")
    await clear_ip_rate_limit(db_session_factory)
    registration_code = await send_code(client, "purpose@example.com")
    assert registration_code

    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "purpose@example.com",
            "code": registration_code,
            "new_password": "new secure password",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_code_cannot_register_an_account(client, db_session_factory):
    await register_user(client, "reset-purpose@example.com")
    await clear_ip_rate_limit(db_session_factory)
    reset_code = await send_reset_code(client, "reset-purpose@example.com")
    assert reset_code

    response = await client.post(
        "/system-auth/register",
        json={
            "email": "reset-purpose@example.com",
            "code": reset_code,
            "password": "new secure password",
            "display_name": "Reset Purpose",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_code_is_deleted_at_the_attempt_limit(client, db_session_factory):
    await register_user(client, "attempts@example.com")
    await clear_ip_rate_limit(db_session_factory)
    code = await send_reset_code(client, "attempts@example.com")
    assert code

    for _ in range(_MAX_ATTEMPTS):
        response = await client.post(
            "/system-auth/password-reset/confirm",
            json={
                "email": "attempts@example.com",
                "code": "not-the-code",
                "new_password": "new secure password",
            },
        )
        assert response.status_code == 400

    rejected = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "attempts@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )

    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_expired_code(client, db_session_factory):
    await register_user(client, "expired@example.com")
    await clear_ip_rate_limit(db_session_factory)
    code = await send_reset_code(client, "expired@example.com")
    assert code

    async with db_session_factory() as db:
        await db.execute(
            update(PasswordResetCode)
            .where(PasswordResetCode.email == "expired@example.com")
            .values(expires_at=utc_now_naive() - timedelta(seconds=1))
        )
        await db.commit()

    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "expired@example.com",
            "code": code,
            "new_password": "new secure password",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_password_over_bcrypt_limit(client, db_session_factory):
    await register_user(client, "long-password@example.com")
    await clear_ip_rate_limit(db_session_factory)
    code = await send_reset_code(client, "long-password@example.com")
    assert code

    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "long-password@example.com",
            "code": code,
            "new_password": "密" * 25,
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unknown_email_debug_code_cannot_reset(client):
    sent = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "missing-confirm@example.com"},
    )
    assert sent.status_code == 200

    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "missing-confirm@example.com",
            "code": sent.json()["code"],
            "new_password": "new secure password",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_inactive_account_cannot_reset(client, db_session_factory):
    await register_user(client, "inactive-reset@example.com")
    async with db_session_factory() as db:
        await db.execute(
            update(SystemUser)
            .where(SystemUser.email == "inactive-reset@example.com")
            .values(status="inactive")
        )
        await db.commit()
    await clear_ip_rate_limit(db_session_factory)

    sent = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "inactive-reset@example.com"},
    )
    assert sent.status_code == 200

    response = await client.post(
        "/system-auth/password-reset/confirm",
        json={
            "email": "inactive-reset@example.com",
            "code": sent.json()["code"],
            "new_password": "new secure password",
        },
    )

    assert response.status_code == 400
