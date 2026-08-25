"""Self-service password reset flows for system authentication."""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PasswordResetCode,
    PasswordResetConfirmRequest,
    SystemSession,
    SystemUser,
)
from app.security import hash_password
from app.services.email import send_verification_email
from app.services.system_auth_codes import (
    CODE_TTL_SECONDS,
    MAX_ATTEMPTS,
    check_ip_rate_limit,
    email_is_valid,
    hash_code,
    password_exceeds_bcrypt_limit,
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
        return response

    code_row = PasswordResetCode(
        email=normalized_email,
        code_hash=hash_code(code),
        expires_at=now_naive + timedelta(seconds=CODE_TTL_SECONDS),
    )
    db.add(code_row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        competing_result = await db.execute(
            select(PasswordResetCode.id).where(
                PasswordResetCode.email == normalized_email,
                PasswordResetCode.expires_at > now_naive,
            )
        )
        if competing_result.scalar_one_or_none() is not None:
            return response
        raise

    if not debug:
        sent = await send_verification_email(
            normalized_email,
            code,
            purpose="password_reset",
        )
        if not sent:
            await db.execute(
                delete(PasswordResetCode).where(
                    PasswordResetCode.id == code_row.id,
                    PasswordResetCode.code_hash == code_row.code_hash,
                )
            )
            await db.commit()
            raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return response


async def confirm_password_reset(
    db: AsyncSession,
    *,
    payload: PasswordResetConfirmRequest,
) -> dict[str, str]:
    email = payload.email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if password_exceeds_bcrypt_limit(payload.new_password):
        raise HTTPException(status_code=400, detail="密码长度不能超过 72 字节")

    now_naive = utc_now_naive()
    code_result = await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.email == email,
            PasswordResetCode.expires_at > now_naive,
        )
    )
    code_row = code_result.scalar_one_or_none()
    if code_row is None:
        raise HTTPException(
            status_code=400,
            detail="验证码未发送或已过期，请重新获取",
        )

    code_matches = secrets.compare_digest(
        code_row.code_hash,
        hash_code(payload.code.strip()),
    )
    if not code_matches:
        code_row.attempts += 1
        if code_row.attempts >= MAX_ATTEMPTS:
            await db.delete(code_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码错误")

    user_result = await db.execute(
        select(SystemUser).where(
            SystemUser.email == email,
            SystemUser.status == "active",
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        await db.delete(code_row)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="验证码未发送或已过期，请重新获取",
        )

    user.password_hash = hash_password(payload.new_password)
    await db.delete(code_row)
    await db.execute(
        update(SystemSession)
        .where(
            SystemSession.user_id == user.id,
            SystemSession.revoked_at.is_(None),
        )
        .values(revoked_at=now_naive)
    )
    await db.commit()
    return {"message": "密码已重置，请使用新密码登录"}
