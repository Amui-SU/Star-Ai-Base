from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    KnowledgeBase,
    SystemSession,
    SystemUser,
    Workspace,
    WorkspaceMember,
)
from app.security import SESSION_COOKIE_NAME, hash_token
from app.time_utils import as_aware_utc, utc_now, utc_now_naive


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Not authenticated")


def _session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token

    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


async def _resolve_current_user(
    request: Request,
    db: AsyncSession,
    *,
    touch_last_seen: bool,
) -> SystemUser:
    token = _session_token_from_request(request)
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

    if as_aware_utc(session.expires_at) <= utc_now():
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

    if touch_last_seen:
        session.last_seen_at = utc_now_naive()
        await db.commit()
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUser:
    return await _resolve_current_user(request, db, touch_last_seen=True)


async def get_current_user_readonly(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUser:
    return await _resolve_current_user(request, db, touch_last_seen=False)


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
    workspace = result.scalars().first()
    if workspace is None:
        raise HTTPException(status_code=403, detail="Workspace access required")
    return workspace


async def get_current_workspace_readonly(
    current_user: SystemUser = Depends(get_current_user_readonly),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.id)
    )
    workspace = result.scalars().first()
    if workspace is None:
        raise HTTPException(status_code=403, detail="Workspace access required")
    return workspace


async def get_knowledge_base_for_user(
    knowledge_base_id: int,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.workspace_id == current_workspace.id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return knowledge_base


async def get_knowledge_base_for_user_readonly(
    knowledge_base_id: int,
    current_workspace: Workspace = Depends(get_current_workspace_readonly),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.workspace_id == current_workspace.id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return knowledge_base
