"""Registration flow helpers for system authentication."""

import secrets

from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SystemAuthResponse,
    SystemRegisterRequest,
    SystemUser,
    VerificationCode,
    Workspace,
    WorkspaceMember,
)
from app.security import hash_password
from app.services.system_auth_codes import (
    MAX_ATTEMPTS,
    email_is_valid,
    hash_code,
    password_exceeds_bcrypt_limit,
)
from app.services.system_auth_responses import user_response, workspace_response
from app.services.system_auth_sessions import create_system_session
from app.time_utils import utc_now_naive


def duplicate_email_exception() -> HTTPException:
    return HTTPException(status_code=400, detail="邮箱已注册")


async def register_system_user(
    db: AsyncSession,
    *,
    payload: SystemRegisterRequest,
    response: Response,
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    display_name = payload.display_name.strip()

    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if password_exceeds_bcrypt_limit(payload.password):
        raise HTTPException(status_code=400, detail="密码长度不能超过 72 字节")

    now_naive = utc_now_naive()
    code_result = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.expires_at > now_naive,
        )
    )
    code_row = code_result.scalar_one_or_none()

    if code_row is None:
        raise HTTPException(status_code=400, detail="验证码未发送或已过期，请重新获取")

    if code_row.attempts >= MAX_ATTEMPTS:
        await db.delete(code_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新获取")

    if not secrets.compare_digest(code_row.code_hash, hash_code(payload.code.strip())):
        code_row.attempts += 1
        await db.commit()
        remaining = MAX_ATTEMPTS - code_row.attempts
        raise HTTPException(
            status_code=400,
            detail=f"验证码错误，还剩 {remaining} 次尝试",
        )

    await db.delete(code_row)
    await db.commit()

    existing_result = await db.execute(
        select(SystemUser).where(SystemUser.email == email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise duplicate_email_exception()

    try:
        user = SystemUser(
            email=email,
            password_hash=hash_password(payload.password),
            display_name=display_name,
            status="active",
        )
        db.add(user)
        await db.flush()

        workspace = Workspace(
            name=f"{display_name} 的个人空间",
            owner_user_id=user.id,
        )
        db.add(workspace)
        await db.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
        db.add(member)
        token = await create_system_session(
            db, user.id, response, credential_version=user.credential_version
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise duplicate_email_exception() from None

    return SystemAuthResponse(
        user=await user_response(db, user),
        workspace=workspace_response(workspace, member),
        session_token=token,
    )
