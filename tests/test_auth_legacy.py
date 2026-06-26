from datetime import timedelta

from sqlalchemy import select

import pytest

from app.models import OAuthPendingState, UserSession
from app.time_utils import utc_now_naive


async def _add_legacy_qrcode_pending_state(db_session_factory, qrcode_key: str):
    async with db_session_factory() as session:
        session.add(
            OAuthPendingState(
                state_key=qrcode_key,
                purpose="legacy_auth_qrcode",
                expires_at=utc_now_naive() + timedelta(minutes=5),
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_qrcode_poll_persists_lowercase_cookie_aliases(
    client,
    db_session_factory,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    await _add_legacy_qrcode_pending_state(db_session_factory, "qr-key")
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


@pytest.mark.asyncio
async def test_legacy_qrcode_generate_persists_pending_state(
    client,
    db_session_factory,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()

    class FakeBilibiliService:
        async def generate_qrcode(self):
            return {
                "qrcode_key": "legacy-generated-qr",
                "qrcode_url": "https://passport.bilibili.com/qrcode",
                "qrcode_image_base64": "base64-image",
            }

        async def close(self):
            pass

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode")

    assert response.status_code == 200
    async with db_session_factory() as session:
        pending = (
            (
                await session.execute(
                    select(OAuthPendingState).where(
                        OAuthPendingState.state_key == "legacy-generated-qr"
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
    assert pending is not None
    assert pending.purpose == "legacy_auth_qrcode"


@pytest.mark.asyncio
async def test_legacy_qrcode_generate_closes_service_on_upstream_error(
    client,
    monkeypatch,
):
    import app.routers.auth as auth_router

    closed = False

    class FakeBilibiliService:
        async def generate_qrcode(self):
            raise Exception("upstream timeout")

        async def close(self):
            nonlocal closed
            closed = True

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode")

    assert response.status_code == 500
    assert closed is True


@pytest.mark.asyncio
async def test_legacy_qrcode_poll_closes_authenticated_service_on_user_info_error(
    client,
    db_session_factory,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    await _add_legacy_qrcode_pending_state(db_session_factory, "close-auth-qr-key")
    monkeypatch.setattr(auth_router.uuid, "uuid4", lambda: "close-auth-session-id")
    auth_service_closed = False

    class FakeBilibiliService:
        def __init__(self, *args, **kwargs):
            self.is_authenticated_service = bool(kwargs.get("sessdata"))

        async def poll_qrcode_status(self, qrcode_key):
            return {
                "status": "confirmed",
                "message": "登录成功",
                "cookies": {
                    "SESSDATA": "sess",
                    "bili_jct": "csrf",
                    "DedeUserID": "4242",
                },
            }

        async def get_user_info(self):
            raise Exception("user info failed")

        async def close(self):
            nonlocal auth_service_closed
            if self.is_authenticated_service:
                auth_service_closed = True

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode/poll/close-auth-qr-key")

    assert response.status_code == 200
    assert response.json()["session_id"] == "close-auth-session-id"
    assert auth_service_closed is True


@pytest.mark.asyncio
async def test_legacy_qrcode_poll_rejects_unknown_pending_state(
    client,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()

    class FakeBilibiliService:
        async def poll_qrcode_status(self, qrcode_key):
            raise AssertionError("unknown QR keys must not reach upstream polling")

        async def close(self):
            pass

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode/poll/missing-qr")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_legacy_qrcode_poll_rejects_source_binding_pending_session(
    client,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    auth_router._set_session(
        "binding-qr-key",
        {"status": "waiting", "purpose": "source_binding", "user_id": 1},
        auth_router.QRCODE_SESSION_TTL,
    )

    class FakeBilibiliService:
        async def poll_qrcode_status(self, qrcode_key):
            raise AssertionError("source binding QR keys must not reach legacy polling")

        async def close(self):
            pass

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode/poll/binding-qr-key")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_legacy_qrcode_poll_accepts_inflight_unscoped_memory_session(
    client,
    monkeypatch,
):
    import app.routers.auth as auth_router

    auth_router.login_sessions.clear()
    auth_router._set_session(
        "old-memory-qr-key",
        {"status": "waiting"},
        auth_router.QRCODE_SESSION_TTL,
    )

    class FakeBilibiliService:
        async def poll_qrcode_status(self, qrcode_key):
            assert qrcode_key == "old-memory-qr-key"
            return {"status": "waiting", "message": "等待扫码"}

        async def close(self):
            pass

    monkeypatch.setattr(auth_router, "BilibiliService", FakeBilibiliService)

    response = await client.get("/auth/qrcode/poll/old-memory-qr-key")

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
