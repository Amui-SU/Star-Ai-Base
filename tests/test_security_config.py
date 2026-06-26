from fastapi import Response
import pytest

from app.config import Settings, settings
from app.security import _fernet_key, set_session_cookie


def test_settings_default_to_production_safe_debug(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)

    loaded = Settings(_env_file=None)

    assert loaded.debug is False


def test_fernet_key_requires_app_encryption_key_when_not_debug(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(settings, "debug", False)

    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
        _fernet_key()


def test_session_cookie_is_secure_outside_debug_by_default(monkeypatch):
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "session_cookie_secure", None)
    response = Response()

    set_session_cookie(response, "token")

    assert "Secure" in response.headers["set-cookie"]


def test_session_cookie_can_remain_http_only_for_debug(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "session_cookie_secure", None)
    response = Response()

    set_session_cookie(response, "token")

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" not in cookie
