from sqlalchemy import delete

import pytest

from app.models import VerificationIpRateLimit
from app.routers.system_auth import _IP_RATE_MAX
from tests.system_auth.helpers import register_user


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
