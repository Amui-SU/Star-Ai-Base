from fastapi import Response
from cryptography.fernet import Fernet
import pytest
import subprocess
import sys

from app.config import Settings, settings
from app.security import _fernet_key, decrypt_text, encrypt_text, set_session_cookie


def test_settings_default_to_production_safe_debug(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)

    loaded = Settings(_env_file=None)

    assert loaded.debug is False


def test_settings_imports_without_pydantic_field_env_deprecations():
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "import app.config",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_models_import_without_sqlalchemy_declarative_base_deprecations():
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "import app.models",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_settings_read_uppercase_environment_names(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-secret")

    loaded = Settings(_env_file=None)

    assert loaded.llm_provider == "deepseek"
    assert loaded.session_cookie_secure is False
    assert loaded.smtp_port == 2525
    assert loaded.openai_api_key == "dashscope-secret"
    assert loaded.dashscope_api_key == "dashscope-secret"


def test_fernet_key_requires_app_encryption_key_when_not_debug(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(settings, "debug", False)

    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
        _fernet_key()


def test_fernet_key_accepts_passphrase_app_encryption_key(monkeypatch):
    import app.security as security

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "local deployment passphrase")
    monkeypatch.setattr(security, "_fernet_instance", None)

    encrypted = encrypt_text("secret payload")

    assert decrypt_text(encrypted) == "secret payload"


def test_fernet_key_preserves_valid_fernet_key(monkeypatch):
    generated_key = Fernet.generate_key()

    monkeypatch.setenv("APP_ENCRYPTION_KEY", generated_key.decode("utf-8"))

    assert _fernet_key() == generated_key


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
