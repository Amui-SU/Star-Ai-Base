from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models import UserApiAccount


async def register(client, email):
    sent = await client.post("/system-auth/send-code", json={"email": email})
    code = sent.json()["code"]
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Draft User",
            "code": code,
        },
    )
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


class FakeCompletions:
    def __init__(self, captured, error=None):
        self.captured = captured
        self.error = error

    def create(self, **kwargs):
        self.captured["request"] = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[])


def install_fake_client(monkeypatch, *, error=None):
    captured = {}

    def factory(config):
        captured["config"] = config
        return SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions(captured, error)),
            close=lambda: captured.update(closed=True),
        )

    monkeypatch.setattr("app.services.api_account_validation.get_llm_client", factory)
    return captured


@pytest.mark.asyncio
async def test_validate_new_draft_uses_unsaved_config_and_does_not_persist(
    client, db_session_factory, monkeypatch
):
    headers = await register(client, "draft-new@example.com")
    captured = install_fake_client(monkeypatch)

    response = await client.post(
        "/api-accounts/validate-draft",
        json={
            "provider": "deepseek",
            "api_key": "draft-secret",
            "base_url": "https://draft.example/v1",
            "model": "chat-alias",
            "protocol": "openai_compatible",
            "auth_scheme": "bearer",
            "advanced_config": {
                "model_mapping": {"chat-alias": "real-model"},
                "headers": {"X-Tenant": "draft"},
                "body": {"temperature": 0.1},
            },
            "thinking_config": {"reasoning_effort": "low"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["latency_ms"] >= 0
    assert captured["config"]["api_key"] == "draft-secret"
    assert captured["config"]["base_url"] == "https://draft.example/v1"
    assert captured["config"]["protocol"] == "openai_compatible"
    assert captured["request"]["model"] == "real-model"
    assert captured["request"]["messages"] == [{"role": "user", "content": "ping"}]
    assert captured["request"]["stream"] is False
    assert captured["request"]["max_tokens"] == 8
    assert captured["request"]["extra_headers"] == {"X-Tenant": "draft"}
    assert captured["request"]["extra_body"]["temperature"] == 0.1
    assert captured["closed"] is True
    async with db_session_factory() as db:
        assert await db.scalar(select(func.count(UserApiAccount.id))) == 0


@pytest.mark.asyncio
async def test_existing_draft_reuses_key_without_mutating_account(
    client, db_session_factory, monkeypatch
):
    headers = await register(client, "draft-existing@example.com")
    created = await client.post(
        "/api-accounts",
        json={"provider": "claude", "api_key": "saved-secret", "model": "saved-model"},
        headers=headers,
    )
    account_id = created.json()["id"]
    captured = install_fake_client(monkeypatch)

    response = await client.post(
        "/api-accounts/validate-draft",
        json={
            "account_id": account_id,
            "provider": "claude",
            "api_key": "   ",
            "base_url": "https://draft.anthropic.test/v1",
            "model": "draft-model",
            "protocol": "anthropic_messages",
            "auth_scheme": "x_api_key",
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert captured["config"]["api_key"] == "saved-secret"
    assert captured["config"]["protocol"] == "anthropic_messages"
    async with db_session_factory() as db:
        account = await db.get(UserApiAccount, account_id)
        assert account.base_url != "https://draft.anthropic.test/v1"
        assert account.model == "saved-model"
        assert account.last_validated_at is None
        assert account.last_error is None


@pytest.mark.asyncio
async def test_draft_account_lookup_is_owner_scoped(client, monkeypatch):
    alice = await register(client, "draft-alice@example.com")
    bob = await register(client, "draft-bob@example.com")
    client.cookies.clear()
    created = await client.post(
        "/api-accounts",
        json={"provider": "deepseek", "api_key": "alice-secret"},
        headers=alice,
    )
    install_fake_client(monkeypatch)
    response = await client.post(
        "/api-accounts/validate-draft",
        json={
            "account_id": created.json()["id"],
            "provider": "deepseek",
            "api_key": "",
        },
        headers=bob,
    )
    assert response.status_code == 404
    assert "alice-secret" not in response.text


@pytest.mark.asyncio
async def test_existing_draft_cannot_change_provider(client, monkeypatch):
    headers = await register(client, "draft-provider@example.com")
    created = await client.post(
        "/api-accounts",
        json={"provider": "deepseek", "api_key": "saved-secret"},
        headers=headers,
    )
    install_fake_client(monkeypatch)
    response = await client.post(
        "/api-accounts/validate-draft",
        json={"account_id": created.json()["id"], "provider": "claude", "api_key": ""},
        headers=headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_new_draft_missing_key_is_invalid_configuration(client, monkeypatch):
    headers = await register(client, "draft-no-key@example.com")
    install_fake_client(monkeypatch)
    response = await client.post(
        "/api-accounts/validate-draft",
        json={"provider": "deepseek", "api_key": ""},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "invalid_configuration"


def draft_failure(name, status_code=None):
    return type(name, (Exception,), {})("placeholder")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected", "http_status"),
    [
        (draft_failure("AuthenticationError"), "authentication_failed", 401),
        (draft_failure("PermissionDeniedError"), "authentication_failed", 403),
        (draft_failure("NotFoundError"), "model_unavailable", 404),
        (draft_failure("APITimeoutError"), "timeout", None),
        (draft_failure("APIConnectionError"), "endpoint_unreachable", None),
        (draft_failure("BadRequestError"), "invalid_configuration", 400),
    ],
)
async def test_draft_errors_are_classified_without_raw_details(
    client, monkeypatch, error, expected, http_status
):
    headers = await register(client, f"draft-{expected}-{http_status}@example.com")
    error.status_code = http_status
    error.args = ("raw-secret-key X-Tenant-private",)
    install_fake_client(monkeypatch, error=error)
    response = await client.post(
        "/api-accounts/validate-draft",
        json={"provider": "deepseek", "api_key": "raw-secret-key"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected
    assert body["http_status"] == http_status
    assert "raw-secret-key" not in response.text
    assert "X-Tenant-private" not in response.text


@pytest.mark.asyncio
async def test_malformed_advanced_config_returns_local_invalid_configuration(
    client, monkeypatch
):
    headers = await register(client, "draft-malformed@example.com")
    captured = install_fake_client(monkeypatch)
    response = await client.post(
        "/api-accounts/validate-draft",
        json={"provider": "deepseek", "api_key": "secret", "advanced_config": ["bad"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "invalid_configuration"
    assert "request" not in captured
