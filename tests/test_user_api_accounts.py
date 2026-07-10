import pytest


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
