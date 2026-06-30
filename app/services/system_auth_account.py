"""Account self-service flow helpers for system authentication."""

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemDisplayNameUpdateRequest, SystemSession, SystemUserResponse
from app.security import clear_session_cookie, hash_token
from app.services.system_auth_responses import user_response
from app.services.system_auth_sessions import (
    get_current_user,
    session_token_from_request,
)
from app.time_utils import utc_now_naive


async def logout_system_user(
    db: AsyncSession,
    *,
    request: Request,
    response: Response,
) -> dict[str, str]:
    token = session_token_from_request(request)
    if token:
        result = await db.execute(
            select(SystemSession).where(
                SystemSession.session_token_hash == hash_token(token)
            )
        )
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = utc_now_naive()
            await db.commit()

    clear_session_cookie(response)
    return {"message": "已退出登录"}


async def current_system_user_response(
    db: AsyncSession,
    *,
    request: Request,
) -> SystemUserResponse:
    user = await get_current_user(request, db)
    return await user_response(db, user)


async def update_system_display_name(
    db: AsyncSession,
    *,
    payload: SystemDisplayNameUpdateRequest,
    request: Request,
) -> SystemUserResponse:
    user = await get_current_user(request, db)
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(display_name) > 100:
        raise HTTPException(status_code=400, detail="用户名不能超过 100 个字符")

    user.display_name = display_name
    await db.commit()
    await db.refresh(user)
    return await user_response(db, user)
