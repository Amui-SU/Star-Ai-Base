"""Self-service password reset flows for system authentication."""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PasswordResetCode, SystemUser
from app.services.email import send_verification_email
from app.services.system_auth_codes import (
    CODE_TTL_SECONDS,
    check_ip_rate_limit,
    email_is_valid,
    hash_code,
)
from app.time_utils import utc_now_naive

GENERIC_SEND_MESSAGE = "如果该邮箱已注册，重置验证码已发送"


async def send_password_reset_code(
    db: AsyncSession,
    *,
    email: str,
    client_ip: str,
    debug: bool,
) -> dict[str, str]:
    normalized_email = email.strip().lower()
    if not email_is_valid(normalized_email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if not await check_ip_rate_limit(db, client_ip):
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    code = f"{secrets.randbelow(1000000):06d}"
    response = {"message": GENERIC_SEND_MESSAGE}
    if debug:
        response["code"] = code

    user_result = await db.execute(
        select(SystemUser).where(
            SystemUser.email == normalized_email,
            SystemUser.status == "active",
        )
    )
    if user_result.scalar_one_or_none() is None:
        return response

    now_naive = utc_now_naive()
    await db.execute(
        delete(PasswordResetCode).where(PasswordResetCode.expires_at < now_naive)
    )
    existing_result = await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.email == normalized_email,
            PasswordResetCode.expires_at > now_naive,
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=429,
            detail="验证码已发送，请查收邮箱或等待过期后重试",
        )

    db.add(
        PasswordResetCode(
            email=normalized_email,
            code_hash=hash_code(code),
            expires_at=now_naive + timedelta(seconds=CODE_TTL_SECONDS),
        )
    )
    await db.commit()

    if not debug:
        sent = await send_verification_email(normalized_email, code)
        if not sent:
            raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return response
