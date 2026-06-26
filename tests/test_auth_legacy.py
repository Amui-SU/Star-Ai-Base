from sqlalchemy import select

import pytest

from app.models import UserSession


@pytest.mark.asyncio
async def test_qrcode_poll_persists_lowercase_cookie_aliases(
    client,
    db_session_factory,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    monkeypatch.setattr(auth_router.uuid, "uuid4", lambda: "legacy-session-id")

    class FakeBilibiliService:
        def __init__(self, *args, **kwargs):
            self.sessdata = kwargs.get("sessdata")
            self.bili_jct = kwargs.get("bili_jct")
            self.dedeuserid = kwargs.get("dedeuserid")

        async def poll_qrcode_status(self, qrcode_key):
            return {
                "status": "confirmed",
                "message": "登录成功",
                "cookies": {
                    "sessdata": "lower-sess",
                    "bili_jct": "csrf-token",
                    "dedeuserid": "4242",
                },
                "refresh_token": "refresh-token",
            }

        async def get_user_info(self):
            return {
                "mid": int(self.dedeuserid),
                "uname": "Legacy User",
                "face": "https://example.com/avatar.png",
                "level_info": {"current_level": 6},
            }

        async def close(self):
            pass

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode/poll/qr-key")

    assert response.status_code == 200
    assert response.json()["session_id"] == "legacy-session-id"

    async with db_session_factory() as session:
        db_session = (
            (
                await session.execute(
                    select(UserSession).where(
                        UserSession.session_id == "legacy-session-id"
                    )
                )
            )
            .scalars()
            .one()
        )

    assert db_session.sessdata != "lower-sess"
    assert db_session.bili_jct != "csrf-token"
    assert db_session.sessdata.startswith("fernet:")
    assert db_session.bili_jct.startswith("fernet:")
    assert db_session.dedeuserid == "4242"
    assert auth_router.login_sessions["legacy-session-id"]["cookies"] == {
        "SESSDATA": "lower-sess",
        "bili_jct": "csrf-token",
        "DedeUserID": "4242",
    }

    auth_router.login_sessions.clear()
    restored = await auth_router.get_session("legacy-session-id")
    assert restored["cookies"] == {
        "SESSDATA": "lower-sess",
        "bili_jct": "csrf-token",
        "DedeUserID": "4242",
    }


@pytest.mark.asyncio
async def test_legacy_plaintext_bilibili_session_cookies_still_restore(
    client,
    db_session_factory,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    async with db_session_factory() as session:
        session.add(
            UserSession(
                session_id="plaintext-session-id",
                bili_mid=4242,
                bili_uname="Legacy User",
                sessdata="plain-sess",
                bili_jct="plain-csrf",
                dedeuserid="4242",
                is_valid=True,
            )
        )
        await session.commit()

    restored = await auth_router.get_session("plaintext-session-id")

    assert restored["cookies"] == {
        "SESSDATA": "plain-sess",
        "bili_jct": "plain-csrf",
        "DedeUserID": "4242",
    }


@pytest.mark.asyncio
async def test_legacy_logout_revokes_persisted_bilibili_session(
    client,
    db_session_factory,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    async with db_session_factory() as session:
        session.add(
            UserSession(
                session_id="logout-session-id",
                bili_mid=4242,
                bili_uname="Legacy User",
                sessdata="plain-sess",
                bili_jct="plain-csrf",
                dedeuserid="4242",
                is_valid=True,
            )
        )
        await session.commit()

    response = await client.delete("/auth/session/logout-session-id")

    assert response.status_code == 200
    async with db_session_factory() as session:
        db_session = (
            (
                await session.execute(
                    select(UserSession).where(
                        UserSession.session_id == "logout-session-id"
                    )
                )
            )
            .scalars()
            .one()
        )
    assert db_session.is_valid is False
    assert await auth_router.get_session("logout-session-id") is None
