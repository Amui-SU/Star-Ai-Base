"""Password login flow helpers for system authentication."""

from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemAuthResponse, SystemLoginRequest, SystemUser
from app.security import verify_password
from app.services.system_auth_codes import (
    email_is_valid,
    password_exceeds_bcrypt_limit,
)
from app.services.system_auth_responses import user_response, workspace_response
from app.services.system_auth_sessions import (
    create_system_session,
    get_primary_workspace,
)


def invalid_credentials_exception() -> HTTPException:
    return HTTPException(status_code=401, detail="邮箱或密码错误")


async def login_system_user(
    db: AsyncSession,
    *,
    payload: SystemLoginRequest,
    response: Response,
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    result = await db.execute(select(SystemUser).where(SystemUser.email == email))
    user = result.scalar_one_or_none()

    if (
        user is None
        or user.status != "active"
        or password_exceeds_bcrypt_limit(payload.password)
        or not verify_password(payload.password, user.password_hash)
    ):
        raise invalid_credentials_exception()

    credential_version = user.credential_version
    workspace, member = await get_primary_workspace(db, user.id)
    token = await create_system_session(
        db, user.id, response, credential_version=credential_version
    )
    await db.commit()

    return SystemAuthResponse(
        user=await user_response(db, user),
        workspace=workspace_response(workspace, member),
        session_token=token,
    )
