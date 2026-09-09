"""Admin user helpers for system authentication."""

import secrets

from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AdminPasswordResetResponse,
    AdminUserListResponse,
    AdminUserResponse,
    SystemSession,
    SystemUser,
)
from app.security import hash_password
from app.services.system_auth_sessions import get_current_user


def configured_admin_emails() -> set[str]:
    return {
        email.strip().lower()
        for email in settings.admin_emails.split(",")
        if email.strip()
    }


async def is_admin_user(db: AsyncSession, user: SystemUser) -> bool:
    configured = configured_admin_emails()
    if configured:
        return user.email.lower() in configured

    result = await db.execute(select(SystemUser.id).order_by(SystemUser.id).limit(1))
    first_user_id = result.scalar_one_or_none()
    return first_user_id == user.id


async def admin_user_response(db: AsyncSession, user: SystemUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        is_admin=await is_admin_user(db, user),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def get_current_admin_user(request: Request, db: AsyncSession) -> SystemUser:
    user = await get_current_user(request, db)
    if not await is_admin_user(db, user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def list_admin_users(db: AsyncSession) -> AdminUserListResponse:
    result = await db.execute(select(SystemUser).order_by(SystemUser.id))
    users = result.scalars().all()
    return AdminUserListResponse(
        users=[await admin_user_response(db, user) for user in users]
    )


async def update_admin_user_status(
    db: AsyncSession,
    admin: SystemUser,
    user_id: int,
    requested_status: str,
) -> AdminUserResponse:
    next_status = requested_status.strip().lower()
    if next_status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="用户状态只能是 active 或 inactive")
    if admin.id == user_id and next_status != "active":
        raise HTTPException(status_code=400, detail="不能禁用当前管理员账号")

    result = await db.execute(select(SystemUser).where(SystemUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.status = next_status
    if next_status == "inactive":
        await db.execute(delete(SystemSession).where(SystemSession.user_id == user_id))
    await db.commit()
    await db.refresh(user)
    return await admin_user_response(db, user)


async def reset_admin_user_password(
    db: AsyncSession,
    admin: SystemUser,
    user_id: int,
) -> AdminPasswordResetResponse:
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="不能重置当前管理员账号密码")

    result = await db.execute(select(SystemUser).where(SystemUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    temporary_password = secrets.token_urlsafe(18)
    await db.execute(
        update(SystemUser)
        .where(SystemUser.id == user_id)
        .values(
            password_hash=hash_password(temporary_password),
            credential_version=SystemUser.credential_version + 1,
            status="active",
        )
    )
    await db.execute(delete(SystemSession).where(SystemSession.user_id == user_id))
    await db.commit()
    await db.refresh(user)
    return AdminPasswordResetResponse(
        user=await admin_user_response(db, user),
        temporary_password=temporary_password,
    )
