import pytest
from types import SimpleNamespace

from app.security import decrypt_text
from app.services.api_credentials import (
    account_response,
    resolved_credential_from_account,
)


def test_provider_defaults_include_agnes_and_claude():
    from app.services.api_credentials import provider_defaults

    assert provider_defaults("agnes").base_url == "https://apihub.agnes-ai.com/v1"
    assert provider_defaults("agnes").model == "agnes-2.0-flash"
    assert provider_defaults("claude").base_url == "https://api.anthropic.com/v1"
    assert provider_defaults("claude").model == "claude-haiku-4-5"


async def _send_code(client, email: str) -> str:
    response = await client.post("/system-auth/send-code", json={"email": email})
    assert response.status_code == 200
    code = response.json().get("code")
    assert code
    return code


async def _register_user(
    client,
    email: str,
    *,
    display_name: str = "API User",
    password: str = "correct horse battery staple",
) -> dict:
    code = await _send_code(client, email)
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_user_can_create_list_and_delete_own_api_account(client):
    auth = await _register_user(client, "api-owner@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "display_name": "我的 DeepSeek",
            "api_key": "sk-user-secret",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=headers,
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["provider"] == "deepseek"
    assert payload["provider_label"] == "DeepSeek"
    assert payload["display_name"] == "我的 DeepSeek"
    assert payload["configured"] is True
    assert payload["is_default"] is True
    assert "api_key" not in payload
    assert "sk-user-secret" not in str(payload)

    listing = await client.get("/api-accounts", headers=headers)
    assert listing.status_code == 200
    accounts = listing.json()
    assert len(accounts) == 1
    assert accounts[0]["display_name"] == "我的 DeepSeek"
    assert "api_key" not in accounts[0]
    assert "sk-user-secret" not in str(accounts)

    deleted = await client.delete(f"/api-accounts/{payload['id']}", headers=headers)
    assert deleted.status_code == 204

    after_delete = await client.get("/api-accounts", headers=headers)
    assert after_delete.status_code == 200
    assert after_delete.json() == []


@pytest.mark.asyncio
async def test_user_api_accounts_are_isolated_by_owner(client):
    alice = await _register_user(client, "alice-api@example.com", display_name="Alice")
    bob = await _register_user(client, "bob-api@example.com", display_name="Bob")
    client.cookies.clear()
    alice_headers = {"Authorization": f"Bearer {alice['session_token']}"}
    bob_headers = {"Authorization": f"Bearer {bob['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "display_name": "Alice Key",
            "api_key": "alice-secret",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=alice_headers,
    )
    assert created.status_code == 200
    account_id = created.json()["id"]

    bob_list = await client.get("/api-accounts", headers=bob_headers)
    assert bob_list.status_code == 200
    assert bob_list.json() == []

    bob_patch = await client.patch(
        f"/api-accounts/{account_id}",
        json={"display_name": "Stolen"},
        headers=bob_headers,
    )
    assert bob_patch.status_code == 404

    bob_delete = await client.delete(f"/api-accounts/{account_id}", headers=bob_headers)
    assert bob_delete.status_code == 404


@pytest.mark.asyncio
async def test_user_can_update_api_account_without_retyping_key(client):
    auth = await _register_user(client, "api-update@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "kimi",
            "api_key": "kimi-secret",
            "model": "moonshot-v1-8k",
            "is_default": True,
        },
        headers=headers,
    )
    assert created.status_code == 200
    account_id = created.json()["id"]

    updated = await client.patch(
        f"/api-accounts/{account_id}",
        json={
            "display_name": "Updated Kimi",
            "model": "moonshot-v1-32k",
        },
        headers=headers,
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["display_name"] == "Updated Kimi"
    assert body["model"] == "moonshot-v1-32k"
    assert body["configured"] is True
    assert "kimi-secret" not in str(body)


@pytest.mark.asyncio
async def test_user_can_set_one_default_api_account(client):
    auth = await _register_user(client, "api-default@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    deepseek = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "deepseek-secret",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=headers,
    )
    kimi = await client.post(
        "/api-accounts",
        json={
            "provider": "kimi",
            "api_key": "kimi-secret",
            "model": "moonshot-v1-8k",
        },
        headers=headers,
    )
    assert deepseek.status_code == 200
    assert kimi.status_code == 200

    switched = await client.post(
        f"/api-accounts/{kimi.json()['id']}/set-default",
        headers=headers,
    )
    assert switched.status_code == 200
    assert switched.json()["is_default"] is True

    listing = await client.get("/api-accounts", headers=headers)
    assert listing.status_code == 200
    by_provider = {account["provider"]: account for account in listing.json()}
    assert by_provider["deepseek"]["is_default"] is False
    assert by_provider["kimi"]["is_default"] is True


@pytest.mark.asyncio
async def test_api_account_expanded_fields_round_trip_and_update(
    client, db_session_factory
):
    auth = await _register_user(client, "api-expanded@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "expanded-secret",
            "model": "chat-alias",
            "protocol": "openai_compatible",
            "auth_scheme": "bearer",
            "website_url": "https://example.test/models",
            "notes": "team gateway",
            "advanced_config": {
                "model_mapping": {"chat-alias": "deepseek-chat"},
                "fallback_model": "chat-alias",
                "headers": {"X-Tenant": "alpha"},
                "vendor_extension": {"region": "cn"},
            },
        },
        headers=headers,
    )

    assert created.status_code == 200
    body = created.json()
    assert body["protocol"] == "openai_compatible"
    assert body["auth_scheme"] == "bearer"
    assert body["website_url"] == "https://example.test/models"
    assert body["notes"] == "team gateway"
    assert body["advanced_config"]["model_mapping"] == {"chat-alias": "deepseek-chat"}
    assert body["advanced_config"]["vendor_extension"] == {"region": "cn"}
    assert body["advanced_config"]["fallback_model"] == body["model"]
    assert "api_key" not in body
    account_id = body["id"]

    updated = await client.patch(
        f"/api-accounts/{account_id}",
        json={
            "api_key": "   ",
            "model": "new-alias",
            "website_url": "https://updated.example.test",
            "notes": "updated",
            "advanced_config": {
                "model_mapping": {"new-alias": "deepseek-reasoner"},
                "fallback_model": "",
                "body": {"top_p": 0.8},
            },
        },
        headers=headers,
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["model"] == "new-alias"
    assert updated_body["advanced_config"]["fallback_model"] == "new-alias"
    assert updated_body["advanced_config"]["body"] == {"top_p": 0.8}
    assert updated_body["website_url"] == "https://updated.example.test"
    assert updated_body["notes"] == "updated"

    from app.models import UserApiAccount

    async with db_session_factory() as db:
        account = await db.get(UserApiAccount, account_id)
        assert decrypt_text(account.api_key_encrypted) == "expanded-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"protocol": "anthropic_messages"},
        {"auth_scheme": "x_api_key"},
        {"advanced_config": {"headers": {"Authorization": "secret"}}},
        {"advanced_config": ["not", "an", "object"]},
    ],
)
async def test_api_account_rejects_unsafe_provider_settings(client, payload):
    auth = await _register_user(client, f"unsafe-{next(iter(payload))}@example.com")
    client.cookies.clear()
    response = await client.post(
        "/api-accounts",
        json={"provider": "deepseek", "api_key": "safe-key", **payload},
        headers={"Authorization": f"Bearer {auth['session_token']}"},
    )

    assert response.status_code == 400
    assert "safe-key" not in response.text


def test_legacy_account_response_infers_provider_defaults_without_mutation():
    account = SimpleNamespace(
        id=7,
        provider="deepseek",
        display_name="Legacy",
        api_key_encrypted="encrypted",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        thinking_config=None,
        protocol=None,
        auth_scheme=None,
        website_url=None,
        notes=None,
        advanced_config=None,
        enabled=True,
        is_default=False,
        last_validated_at=None,
        last_error=None,
    )

    response = account_response(account)

    assert response.protocol == "openai_compatible"
    assert response.auth_scheme == "bearer"
    assert response.website_url == "https://www.deepseek.com/"
    assert response.advanced_config["fallback_model"] == "deepseek-chat"
    assert account.protocol is None
    assert account.advanced_config is None


def test_resolved_credential_maps_account_model_alias_and_keeps_legacy_fallback(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.api_credentials.decrypt_api_key", lambda _encrypted: "secret"
    )
    account = SimpleNamespace(
        id=9,
        provider="deepseek",
        api_key_encrypted="encrypted",
        base_url="https://gateway.example.test/v1",
        model="chat-alias",
        thinking_config={},
        protocol="openai_compatible",
        auth_scheme="bearer",
        advanced_config={
            "model_mapping": {"chat-alias": "deepseek-chat"},
            "fallback_model": "fallback-model",
        },
    )

    resolved = resolved_credential_from_account(account)

    assert resolved.model == "deepseek-chat"
    assert resolved.protocol == "openai_compatible"
    assert resolved.auth_scheme == "bearer"
    assert resolved.advanced_config["fallback_model"] == "fallback-model"
    assert resolved.to_llm_config()["advanced_config"] == resolved.advanced_config


@pytest.mark.asyncio
async def test_advanced_config_null_defaults_and_patch_reset_are_explicit(client):
    auth = await _register_user(client, "api-null-config@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "null-config-secret",
            "model": "deepseek-chat",
            "advanced_config": None,
        },
        headers=headers,
    )

    assert created.status_code == 200
    account_id = created.json()["id"]
    assert created.json()["advanced_config"]["fallback_model"] == "deepseek-chat"

    configured = await client.patch(
        f"/api-accounts/{account_id}",
        json={"advanced_config": {"headers": {"X-Tenant": "alpha"}}},
        headers=headers,
    )
    assert configured.status_code == 200
    assert configured.json()["advanced_config"]["headers"] == {"X-Tenant": "alpha"}

    reset = await client.patch(
        f"/api-accounts/{account_id}",
        json={"advanced_config": None},
        headers=headers,
    )
    assert reset.status_code == 200
    assert reset.json()["advanced_config"]["headers"] == {}
    assert reset.json()["advanced_config"]["fallback_model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_patch_non_object_advanced_config_does_not_modify_saved_config(client):
    auth = await _register_user(client, "api-invalid-patch@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "invalid-patch-secret",
            "advanced_config": {"headers": {"X-Tenant": "preserved"}},
        },
        headers=headers,
    )
    account_id = created.json()["id"]

    invalid = await client.patch(
        f"/api-accounts/{account_id}",
        json={"advanced_config": ["not", "an", "object"]},
        headers=headers,
    )

    assert invalid.status_code == 400
    listing = await client.get("/api-accounts", headers=headers)
    assert listing.json()[0]["advanced_config"]["headers"] == {"X-Tenant": "preserved"}
