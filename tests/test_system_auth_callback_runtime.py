from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.services.system_auth_callback_runtime import (
    email_config_status,
    handle_google_oauth_callback,
    handle_qq_oauth_callback,
    handle_wechat_oauth_callback,
    oauth_network_error,
)


class FakeLogger:
    def __init__(self):
        self.errors = []
        self.exceptions = []

    def error(self, message):
        self.errors.append(message)

    def exception(self, message):
        self.exceptions.append(message)


async def fake_validate_state(_request, _state):
    return {"frontend_url": "http://localhost:3000", "redirect_uri": "https://callback"}


async def fake_redirect(_db, user, frontend_url):
    return {"user": user, "frontend_url": frontend_url}


def test_email_config_status_uses_debug_or_smtp_credentials():
    assert email_config_status(debug=True, smtp_user="", smtp_password="") == {
        "debug": True,
        "smtp_configured": False,
        "email_login_available": True,
    }
    assert (
        email_config_status(debug=False, smtp_user="smtp", smtp_password="secret")[
            "email_login_available"
        ]
        is True
    )
    assert (
        email_config_status(debug=False, smtp_user="smtp", smtp_password="")[
            "email_login_available"
        ]
        is False
    )


def test_oauth_network_error_logs_provider_and_type_without_secret():
    logger = FakeLogger()
    exc = httpx.ConnectError("secret=value")

    result = oauth_network_error("Google", exc, logger=logger)

    assert isinstance(result, HTTPException)
    assert result.status_code == 502
    assert "secret" not in result.detail
    assert logger.errors == ["Google OAuth network request failed: ConnectError"]


@pytest.mark.asyncio
async def test_handle_wechat_oauth_callback_upserts_external_user_and_redirects():
    calls = []

    async def fetch_wechat_user(code, *, async_client_factory):
        calls.append(("fetch", code, async_client_factory))
        return {
            "openid": "token-openid",
            "user_info": {
                "openid": "profile-openid",
                "nickname": "Wechat User",
                "headimgurl": "https://example.com/wx.png",
            },
        }

    async def upsert_user(_db, *args, **kwargs):
        calls.append(("upsert", args, kwargs))
        return SimpleNamespace(id=8)

    result = await handle_wechat_oauth_callback(
        request=object(),
        code="wechat-code",
        error="",
        state="state",
        db=object(),
        settings=SimpleNamespace(
            wechat_client_id="id",
            wechat_client_secret="secret",
        ),
        async_client_factory=object,
        validate_oauth_callback_state=fake_validate_state,
        fetch_wechat_oauth_user=fetch_wechat_user,
        upsert_oauth_user=upsert_user,
        redirect_with_oauth_session=fake_redirect,
        wechat_redirect_uri=lambda: "https://callback",
        logger=FakeLogger(),
    )

    assert result["frontend_url"] == "http://localhost:3000"
    assert calls[0] == ("fetch", "wechat-code", object)
    assert calls[1] == (
        "upsert",
        ("wechat", "profile-openid", "Wechat User", "https://example.com/wx.png"),
        {},
    )


@pytest.mark.asyncio
async def test_handle_qq_oauth_callback_upserts_openid_user_and_redirects():
    calls = []

    async def fetch_qq_user(code, state_data, *, async_client_factory):
        calls.append(("fetch", code, state_data, async_client_factory))
        return {
            "openid": "qq-openid",
            "user_info": {
                "nickname": "QQ User",
                "figureurl_qq_1": "https://example.com/qq-small.png",
                "figureurl_qq_2": "https://example.com/qq-large.png",
            },
        }

    async def upsert_user(_db, *args, **kwargs):
        calls.append(("upsert", args, kwargs))
        return SimpleNamespace(id=9)

    result = await handle_qq_oauth_callback(
        request=object(),
        code="qq-code",
        error="",
        state="state",
        db=object(),
        settings=SimpleNamespace(qq_client_id="id", qq_client_secret="secret"),
        async_client_factory=object,
        validate_oauth_callback_state=fake_validate_state,
        fetch_qq_oauth_user=fetch_qq_user,
        upsert_oauth_user=upsert_user,
        redirect_with_oauth_session=fake_redirect,
        qq_redirect_uri=lambda: "https://callback",
        logger=FakeLogger(),
    )

    assert result["frontend_url"] == "http://localhost:3000"
    assert calls[1] == (
        "upsert",
        ("qq", "qq-openid", "QQ User", "https://example.com/qq-large.png"),
        {},
    )


@pytest.mark.asyncio
async def test_handle_google_oauth_callback_normalizes_verified_email_user():
    calls = []

    async def fetch_google_user(code, state_data, *, async_client_factory):
        calls.append(("fetch", code, state_data, async_client_factory))
        return {
            "verified_email": True,
            "email": "Person@Example.COM ",
            "name": "Person",
            "picture": "",
        }

    async def upsert_user(_db, *args, **kwargs):
        calls.append(("upsert", args, kwargs))
        return SimpleNamespace(id=10)

    result = await handle_google_oauth_callback(
        request=object(),
        code="google-code",
        error="",
        state="state",
        db=object(),
        settings=SimpleNamespace(
            google_client_id="id",
            google_client_secret="secret",
        ),
        async_client_factory=object,
        validate_oauth_callback_state=fake_validate_state,
        fetch_google_oauth_user=fetch_google_user,
        upsert_oauth_user=upsert_user,
        redirect_with_oauth_session=fake_redirect,
        logger=FakeLogger(),
    )

    assert result["frontend_url"] == "http://localhost:3000"
    assert calls[1] == (
        "upsert",
        ("google", "person@example.com", "Person", None),
        {"email": "person@example.com", "update_default_display_name": False},
    )


@pytest.mark.asyncio
async def test_handle_google_oauth_callback_sanitizes_network_errors():
    logger = FakeLogger()

    async def failing_fetch(_code, _state_data, *, async_client_factory):
        raise httpx.ConnectError("secret=google-secret")

    with pytest.raises(HTTPException) as exc_info:
        await handle_google_oauth_callback(
            request=object(),
            code="google-code",
            error="",
            state="state",
            db=object(),
            settings=SimpleNamespace(
                google_client_id="id",
                google_client_secret="secret",
            ),
            async_client_factory=object,
            validate_oauth_callback_state=fake_validate_state,
            fetch_google_oauth_user=failing_fetch,
            upsert_oauth_user=lambda *_args, **_kwargs: None,
            redirect_with_oauth_session=fake_redirect,
            logger=logger,
        )

    assert exc_info.value.status_code == 502
    assert "secret" not in exc_info.value.detail
    assert logger.errors == ["Google OAuth network request failed: ConnectError"]
