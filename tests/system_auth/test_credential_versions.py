import asyncio

import pytest
from fastapi import HTTPException, Request, Response

from app.dependencies import get_current_user_readonly
from app.models import SystemLoginRequest, SystemUser, PasswordResetConfirmRequest
from app.services.system_auth_admin import reset_admin_user_password
from app.services.system_auth_login import login_system_user
from app.services.system_auth_password_reset import confirm_password_reset
from app.services.system_auth_sessions import get_current_user
from tests.system_auth.helpers import register_user
from tests.system_auth.test_password_reset import send_reset_code


def bearer_request(token):
    return Request(
        {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver", [get_current_user, get_current_user_readonly])
async def test_preloaded_session_observes_revocation_without_password_change(
    client, db_session_factory, resolver
):
    from sqlalchemy import select, update
    from app.models import SystemSession
    from app.time_utils import utc_now_naive

    member = await register_user(client, "member@example.com")
    async with db_session_factory() as cached_db:
        cached = await cached_db.scalar(select(SystemSession))
        async with db_session_factory() as other_db:
            await other_db.execute(
                update(SystemSession).values(revoked_at=utc_now_naive())
            )
            await other_db.commit()
        with pytest.raises(HTTPException) as failure:
            await resolver(bearer_request(member["session_token"]), cached_db)
        assert failure.value.status_code == 401
        assert cached.revoked_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("reset_kind", ["self_service", "admin"])
async def test_late_old_password_login_is_rejected_after_reset(
    client, db_session_factory, monkeypatch, reset_kind
):
    admin_data = await register_user(client, "admin@example.com")
    member = await register_user(client, "member@example.com", password="old-password")
    code = await send_reset_code(client, "member@example.com")
    verified, resume = asyncio.Event(), asyncio.Event()
    import app.services.system_auth_login as login_module

    get_workspace = login_module.get_primary_workspace

    async def paused_workspace(db, user_id):
        verified.set()
        await asyncio.wait_for(resume.wait(), 5)
        return await get_workspace(db, user_id)

    monkeypatch.setattr(login_module, "get_primary_workspace", paused_workspace)

    async def late_login():
        async with db_session_factory() as db:
            return await login_system_user(
                db,
                payload=SystemLoginRequest(
                    email="member@example.com", password="old-password"
                ),
                response=Response(),
            )

    task = asyncio.create_task(late_login())
    try:
        await asyncio.wait_for(verified.wait(), 5)
        async with db_session_factory() as db:
            if reset_kind == "self_service":
                await confirm_password_reset(
                    db,
                    payload=PasswordResetConfirmRequest(
                        email="member@example.com",
                        code=code,
                        new_password="new-password",
                    ),
                )
                new_password = "new-password"
            else:
                admin = await db.get(SystemUser, admin_data["user"]["id"])
                reset = await reset_admin_user_password(db, admin, member["user"]["id"])
                new_password = reset.temporary_password
        resume.set()
        result = await asyncio.wait_for(task, 5)
    finally:
        resume.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    for resolver in (get_current_user, get_current_user_readonly):
        async with db_session_factory() as db:
            with pytest.raises(HTTPException) as failure:
                await resolver(bearer_request(result.session_token), db)
            assert failure.value.status_code == 401

    async with db_session_factory() as db:
        fresh = await login_system_user(
            db,
            payload=SystemLoginRequest(
                email="member@example.com", password=new_password
            ),
            response=Response(),
        )
    for resolver in (get_current_user, get_current_user_readonly):
        async with db_session_factory() as db:
            user = await resolver(bearer_request(fresh.session_token), db)
            assert user.id == member["user"]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver", [get_current_user, get_current_user_readonly])
async def test_resolver_rejects_reset_even_with_preloaded_identity_map(
    client, db_session_factory, resolver
):
    member = await register_user(client, "member@example.com")
    code = await send_reset_code(client, "member@example.com")
    async with db_session_factory() as cached_db:
        cached_user = await cached_db.get(SystemUser, member["user"]["id"])
        async with db_session_factory() as reset_db:
            await confirm_password_reset(
                reset_db,
                payload=PasswordResetConfirmRequest(
                    email="member@example.com",
                    code=code,
                    new_password="changed-password",
                ),
            )
        with pytest.raises(HTTPException) as failure:
            await resolver(bearer_request(member["session_token"]), cached_db)
        assert failure.value.status_code == 401
        assert cached_user.id == member["user"]["id"]


@pytest.mark.asyncio
async def test_oauth_session_after_reset_uses_current_credential_version(
    client, db_session_factory
):
    from app.services.system_auth_oauth_flow import redirect_with_oauth_session
    from app.security import SESSION_COOKIE_NAME
    from http.cookies import SimpleCookie

    member = await register_user(client, "member@example.com")
    code = await send_reset_code(client, "member@example.com")
    async with db_session_factory() as db:
        await confirm_password_reset(
            db,
            payload=PasswordResetConfirmRequest(
                email="member@example.com", code=code, new_password="new-password"
            ),
        )
        user = await db.get(SystemUser, member["user"]["id"])
        redirect = await redirect_with_oauth_session(db, user, "http://localhost:3000")
        cookies = SimpleCookie()
        for header in redirect.headers.getlist("set-cookie"):
            cookies.load(header)
        token = cookies[SESSION_COOKIE_NAME].value
    async with db_session_factory() as db:
        assert (
            await get_current_user_readonly(bearer_request(token), db)
        ).id == member["user"]["id"]
