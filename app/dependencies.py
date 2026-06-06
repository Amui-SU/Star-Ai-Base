from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SystemSession, SystemUser, Workspace, WorkspaceMember
from app.security import SESSION_COOKIE_NAME, hash_token


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Not authenticated")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUser:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _unauthorized()

    result = await db.execute(
        select(SystemSession).where(
            SystemSession.session_token_hash == hash_token(token)
        )
    )
    session = result.scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise _unauthorized()

    if _as_aware_utc(session.expires_at) <= _utc_now():
        raise _unauthorized()

    user_result = await db.execute(
        select(SystemUser).where(
            SystemUser.id == session.user_id,
            SystemUser.status == "active",
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise _unauthorized()

    session.last_seen_at = _utc_now()
    await db.flush()
    return user


async def get_current_workspace(
    current_user: SystemUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=403, detail="Workspace access required")
    return workspace
