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
