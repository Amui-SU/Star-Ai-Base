import asyncio
from datetime import timedelta
from email import message_from_string
from email.header import decode_header, make_header
from unittest.mock import AsyncMock

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update

import pytest

from app.models import (
    PasswordResetCode,
    PasswordResetConfirmRequest,
    SystemUser,
    VerificationIpRateLimit,
)
from app.routers.system_auth import _IP_RATE_MAX, _MAX_ATTEMPTS
from app.services.email import send_verification_email
from app.services.system_auth_password_reset import (
    confirm_password_reset,
    send_password_reset_code,
)
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
async def test_reset_send_hides_a_second_active_code(client, db_session_factory):
    await register_user(client, "duplicate@example.com")
    await clear_ip_rate_limit(db_session_factory)
    assert await send_reset_code(client, "duplicate@example.com")
    await clear_ip_rate_limit(db_session_factory)

    response = await client.post(
        "/system-auth/password-reset/send-code",
        json={"email": "duplicate@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "如果该邮箱已注册，重置验证码已发送"


@pytest.mark.asyncio
async def test_parallel_reset_sends_reserve_one_code_and_deliver_once(
    client, db_session_factory, monkeypatch
):
    await register_user(client, "parallel-send@example.com")
    send_email = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.system_auth_password_reset.send_verification_email", send_email
    )

    async def send(index):
        async with db_session_factory() as db:
            return await send_password_reset_code(
                db,
                email="parallel-send@example.com",
                client_ip=f"parallel-send-{index}",
                debug=False,
            )

    responses = await asyncio.gather(send(1), send(2), return_exceptions=True)
    assert responses == [{"message": "如果该邮箱已注册，重置验证码已发送"}] * 2
    async with db_session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(PasswordResetCode)) == 1
    assert send_email.await_count == 1


@pytest.mark.asyncio
async def test_reset_send_removes_reserved_code_after_delivery_failure(
    client, db_session_factory, monkeypatch
):
    await register_user(client, "delivery-failure@example.com")
    await clear_ip_rate_limit(db_session_factory)
    send_email = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.services.system_auth_password_reset.send_verification_email",
        send_email,
    )

    async with db_session_factory() as db:
        with pytest.raises(HTTPException) as failure:
            await send_password_reset_code(
                db,
                email="delivery-failure@example.com",
                client_ip="delivery-failure-1",
                debug=False,
            )
        assert failure.value.status_code == 500

    async with db_session_factory() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(PasswordResetCode)
            .where(PasswordResetCode.email == "delivery-failure@example.com")
        )
        assert count == 0

    send_email.return_value = True
    async with db_session_factory() as db:
        response = await send_password_reset_code(
            db,
            email="delivery-failure@example.com",
            client_ip="delivery-failure-2",
            debug=False,
        )

    assert response == {"message": "如果该邮箱已注册，重置验证码已发送"}
    assert send_email.await_count == 2


@pytest.mark.asyncio
async def test_password_reset_email_uses_reset_specific_copy(monkeypatch):
    sent_messages: list[str] = []

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def login(self, *_args):
            pass

        def sendmail(self, _sender, _recipients, payload):
            sent_messages.append(payload)

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    monkeypatch.setattr("app.services.email.settings.smtp_use_tls", False)
    monkeypatch.setattr("app.services.email.settings.smtp_user", "smtp@example.com")
    monkeypatch.setattr("app.services.email.settings.smtp_password", "secret")
    monkeypatch.setattr("app.services.email.settings.smtp_from", "")

    sent = await send_verification_email(
        "member@example.com",
        "123456",
        purpose="password_reset",
    )

    assert sent is True
    message = message_from_string(sent_messages[0])
    html = message.get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert str(make_header(decode_header(message["Subject"]))) == (
        "智库云 — 密码重置验证码"
    )
    assert "用于重置 智库云 账号密码" in html
    assert "用于注册" not in html


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
async def test_parallel_invalid_reset_attempts_are_counted_atomically(
    client, db_session_factory
):
    await register_user(client, "parallel-invalid@example.com")
    await clear_ip_rate_limit(db_session_factory)
    assert await send_reset_code(client, "parallel-invalid@example.com")

    async def submit_invalid_code() -> int:
        async with db_session_factory() as db:
            try:
                await confirm_password_reset(
                    db,
                    payload=PasswordResetConfirmRequest(
                        email="parallel-invalid@example.com",
                        code="wrong-code",
                        new_password="new secure password",
                    ),
                )
            except HTTPException as exc:
                return exc.status_code
        return 200

    statuses = await asyncio.gather(
        *(submit_invalid_code() for _ in range(_MAX_ATTEMPTS - 1))
    )

    assert statuses == [400] * (_MAX_ATTEMPTS - 1)
    async with db_session_factory() as db:
        attempts = await db.scalar(
            select(PasswordResetCode.attempts).where(
                PasswordResetCode.email == "parallel-invalid@example.com"
            )
        )
    assert attempts == _MAX_ATTEMPTS - 1
    assert await submit_invalid_code() == 400
    async with db_session_factory() as db:
        assert (
            await db.scalar(
                select(PasswordResetCode.id).where(
                    PasswordResetCode.email == "parallel-invalid@example.com"
                )
            )
            is None
        )


@pytest.mark.asyncio
async def test_parallel_valid_reset_code_is_consumed_atomically(
    client, db_session_factory
):
    await register_user(client, "parallel-valid@example.com")
    await clear_ip_rate_limit(db_session_factory)
    code = await send_reset_code(client, "parallel-valid@example.com")
    assert code

    async def submit_valid_code(new_password: str) -> int:
        async with db_session_factory() as db:
            try:
                await confirm_password_reset(
                    db,
                    payload=PasswordResetConfirmRequest(
                        email="parallel-valid@example.com",
                        code=code,
                        new_password=new_password,
                    ),
                )
            except HTTPException as exc:
                return exc.status_code
        return 200

    statuses = await asyncio.gather(
        submit_valid_code("first secure password"),
        submit_valid_code("second secure password"),
    )

    assert sorted(statuses) == [200, 400]


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
