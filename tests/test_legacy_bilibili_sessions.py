import pytest

from app.models import UserSession
from app.services import legacy_bilibili_sessions as sessions


def test_legacy_session_cache_expires_with_configured_ttl(monkeypatch):
    sessions.login_sessions.clear()
    now = 1_000.0
    monkeypatch.setattr(sessions.time, "time", lambda: now)

    sessions._set_session("session-id", {"cookies": {"SESSDATA": "sess"}}, ttl=10)
    assert sessions._get_session("session-id")["cookies"]["SESSDATA"] == "sess"

    now = 1_011.0
    assert sessions._get_session("session-id") is None
    assert "session-id" not in sessions.login_sessions


@pytest.mark.asyncio
async def test_legacy_session_service_restores_encrypted_db_cookies(
    db_session_factory,
    monkeypatch,
):
    import app.security as security
    import app.database as database

    monkeypatch.setenv("APP_ENCRYPTION_KEY", "legacy bilibili session test key")
    monkeypatch.setattr(security, "_fernet_instance", None)
    monkeypatch.setattr(database, "async_session_factory", db_session_factory)
    sessions.login_sessions.clear()
    async with db_session_factory() as db:
        db.add(
            UserSession(
                session_id="db-session-id",
                bili_mid=123,
                bili_uname="DB User",
                bili_face="https://example.com/avatar.png",
                sessdata=sessions._encrypt_session_cookie("stored-sess"),
                bili_jct=sessions._encrypt_session_cookie("stored-csrf"),
                dedeuserid="123",
                is_valid=True,
            )
        )
        await db.commit()

    restored = await sessions.get_session("db-session-id")

    assert restored["cookies"] == {
        "SESSDATA": "stored-sess",
        "bili_jct": "stored-csrf",
        "DedeUserID": "123",
    }
    assert sessions.login_sessions["db-session-id"]["user_info"]["uname"] == "DB User"
