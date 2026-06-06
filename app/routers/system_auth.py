from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    SystemAuthResponse,
    SystemLoginRequest,
    SystemRegisterRequest,
    SystemSession,
    SystemUser,
    SystemUserResponse,
    Workspace,
    WorkspaceMember,
    WorkspaceResponse,
)
from app.security import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session_token,
    hash_password,
    hash_token,
    session_expires_at,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/system-auth", tags=["系统认证"])

MAX_BCRYPT_PASSWORD_BYTES = 72


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES


def _duplicate_email_exception() -> HTTPException:
    return HTTPException(status_code=400, detail="邮箱已注册")


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(status_code=401, detail="邮箱或密码错误")


def _user_response(user: SystemUser) -> SystemUserResponse:
    return SystemUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


def _workspace_response(
    workspace: Workspace, member: WorkspaceMember
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=member.role,
    )


async def _create_system_session(
    db: AsyncSession, user_id: int, response: Response
) -> None:
    token = create_session_token()
    db.add(
        SystemSession(
            user_id=user_id,
            session_token_hash=hash_token(token),
            expires_at=session_expires_at(),
        )
    )
    set_session_cookie(response, token)


async def _get_primary_workspace(
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


async def _get_current_user(request: Request, db: AsyncSession) -> SystemUser:
    token = request.cookies.get(SESSION_COOKIE_NAME)
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

    if _as_aware_utc(session.expires_at) <= _utc_now():
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    user_result = await db.execute(
        select(SystemUser).where(SystemUser.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    session.last_seen_at = _naive_utc_now()
    await db.commit()
    return user


@router.post("/register", response_model=SystemAuthResponse)
async def register(
    payload: SystemRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    display_name = payload.display_name.strip()

    if _password_exceeds_bcrypt_limit(payload.password):
        raise HTTPException(status_code=400, detail="密码长度不能超过 72 字节")

    existing_result = await db.execute(
        select(SystemUser).where(SystemUser.email == email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise _duplicate_email_exception()

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
        await _create_system_session(db, user.id, response)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _duplicate_email_exception() from None

    return SystemAuthResponse(
        user=_user_response(user),
        workspace=_workspace_response(workspace, member),
    )


@router.post("/login", response_model=SystemAuthResponse)
async def login(
    payload: SystemLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SystemAuthResponse:
    email = payload.email.strip().lower()
    result = await db.execute(select(SystemUser).where(SystemUser.email == email))
    user = result.scalar_one_or_none()

    if (
        user is None
        or user.status != "active"
        or _password_exceeds_bcrypt_limit(payload.password)
        or not verify_password(payload.password, user.password_hash)
    ):
        raise _invalid_credentials_exception()

    workspace, member = await _get_primary_workspace(db, user.id)
    await _create_system_session(db, user.id, response)
    await db.commit()

    return SystemAuthResponse(
        user=_user_response(user),
        workspace=_workspace_response(workspace, member),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        result = await db.execute(
            select(SystemSession).where(
                SystemSession.session_token_hash == hash_token(token)
            )
        )
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = _naive_utc_now()
            await db.commit()

    clear_session_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=SystemUserResponse)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemUserResponse:
    user = await _get_current_user(request, db)
    return _user_response(user)
