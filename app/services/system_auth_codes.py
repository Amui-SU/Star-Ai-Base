"""Email verification code helpers for system authentication."""

import hashlib
import re
import secrets
import time
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VerificationCode, VerificationIpRateLimit
from app.services.email import send_verification_email
from app.time_utils import utc_now_naive

MAX_BCRYPT_PASSWORD_BYTES = 72
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
CODE_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
IP_RATE_MAX = 3
IP_RATE_WINDOW = 60

# Database rows are the source of truth; this map remains for legacy diagnostics.
ip_rate_limit = {}


def cleanup_rate_limits() -> None:
    now = time.time()
    expired = [
        ip for ip, (_, start) in ip_rate_limit.items() if now - start > IP_RATE_WINDOW
    ]
    for ip in expired:
        del ip_rate_limit[ip]


def check_rate_limit(client_ip: str) -> bool:
    cleanup_rate_limits()
    entry = ip_rate_limit.get(client_ip)
    now = time.time()
    if entry is None:
        ip_rate_limit[client_ip] = (1, now)
        return True
    count, start = entry
    if now - start > IP_RATE_WINDOW:
        ip_rate_limit[client_ip] = (1, now)
        return True
    if count >= IP_RATE_MAX:
        return False
    ip_rate_limit[client_ip] = (count + 1, start)
    return True


async def check_ip_rate_limit(db: AsyncSession, client_ip: str) -> bool:
    now_naive = utc_now_naive()
    window_expires_before = now_naive - timedelta(seconds=IP_RATE_WINDOW)
    await db.execute(
        delete(VerificationIpRateLimit).where(
            VerificationIpRateLimit.window_start < window_expires_before,
            VerificationIpRateLimit.ip_address != client_ip,
        )
    )
    expired = VerificationIpRateLimit.window_start < window_expires_before
    for _ in range(3):
        result = await db.execute(
            update(VerificationIpRateLimit)
            .where(
                VerificationIpRateLimit.ip_address == client_ip,
                or_(expired, VerificationIpRateLimit.count < IP_RATE_MAX),
            )
            .values(
                count=case((expired, 1), else_=VerificationIpRateLimit.count + 1),
                window_start=case(
                    (expired, now_naive), else_=VerificationIpRateLimit.window_start
                ),
                updated_at=now_naive,
            )
            .returning(VerificationIpRateLimit.ip_address)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is not None:
            await db.commit()
            return True
        existing = await db.scalar(
            select(VerificationIpRateLimit.ip_address).where(
                VerificationIpRateLimit.ip_address == client_ip
            )
        )
        if existing is not None:
            await db.commit()
            return False
        try:
            async with db.begin_nested():
                db.add(
                    VerificationIpRateLimit(
                        ip_address=client_ip,
                        count=1,
                        window_start=now_naive,
                        updated_at=now_naive,
                    )
                )
                await db.flush()
        except IntegrityError:
            continue
        await db.commit()
        return True
    await db.rollback()
    return False


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def email_is_valid(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES


async def send_verification_code(
    db: AsyncSession,
    *,
    email: str,
    client_ip: str,
    debug: bool,
) -> dict:
    email = email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    if not await check_ip_rate_limit(db, client_ip):
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    now_naive = utc_now_naive()
    await db.execute(
        delete(VerificationCode).where(VerificationCode.expires_at < now_naive)
    )

    existing = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.expires_at > now_naive,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=429,
            detail="验证码已发送，请查收邮箱或等待过期后重试",
        )

    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = now_naive + timedelta(seconds=CODE_TTL_SECONDS)

    db.add(
        VerificationCode(
            email=email,
            code_hash=hash_code(code),
            expires_at=expires_at,
        )
    )
    await db.commit()

    response: dict = {"message": "验证码已发送"}
    if debug:
        response["code"] = code
    else:
        sent = await send_verification_email(email, code)
        if not sent:
            raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return response
