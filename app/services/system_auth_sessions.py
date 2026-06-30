"""System authentication session helpers."""

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSession, SystemUser, Workspace, WorkspaceMember
from app.security import (
    SESSION_COOKIE_NAME,
    create_session_token,
    hash_token,
    session_expires_at,
    set_session_cookie,
)
from app.time_utils import as_aware_utc, utc_now, utc_now_naive


def session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token

    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


async def create_system_session(
    db: AsyncSession, user_id: int, response: Response
) -> str:
    token = create_session_token()
    db.add(
        SystemSession(
            user_id=user_id,
            session_token_hash=hash_token(token),
            expires_at=session_expires_at().replace(tzinfo=None),
        )
    )
    set_session_cookie(response, token)
    return token


async def get_primary_workspace(
    db: AsyncSession, user_id: int
) -> tuple[Workspace, WorkspaceMember]:
    result = await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(WorkspaceMember.id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    return row


async def get_current_user(request: Request, db: AsyncSession) -> SystemUser:
    token = session_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    result = await db.execute(
        select(SystemSession).where(
            SystemSession.session_token_hash == hash_token(token)
        )
    )
    session = result.scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    if as_aware_utc(session.expires_at) <= utc_now():
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    user_result = await db.execute(
        select(SystemUser).where(SystemUser.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    session.last_seen_at = utc_now_naive()
    await db.commit()
    return user
