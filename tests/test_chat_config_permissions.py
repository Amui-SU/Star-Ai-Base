import pytest


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
    password: str = "correct horse battery staple",
    display_name: str = "Test User",
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
async def test_regular_user_cannot_write_global_llm_config(client):
    await _register_user(client, "admin@example.com", display_name="Admin")
    member = await _register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.post(
        "/chat/llm/provider-config",
        json={
            "provider": "deepseek",
            "api_key": "member-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "thinking_mode": "off",
        },
        headers={"Authorization": f"Bearer {member['session_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_switch_global_llm_provider(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "deepseek_api_key", "configured-key")
    await _register_user(client, "admin@example.com", display_name="Admin")
    member = await _register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.post(
        "/chat/llm/config",
        json={"provider": "deepseek"},
        headers={"Authorization": f"Bearer {member['session_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_write_global_web_search_config(client):
    await _register_user(client, "admin@example.com", display_name="Admin")
    member = await _register_user(client, "member@example.com", display_name="Member")
    client.cookies.clear()

    response = await client.post(
        "/chat/web-search/config",
        json={
            "provider": "tavily",
            "tavily_api_key": "member-tavily-key",
            "fallback_html": True,
            "tavily_search_depth": "basic",
        },
        headers={"Authorization": f"Bearer {member['session_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_write_global_llm_and_web_search_config(client, monkeypatch):
    import app.routers.chat as chat_router

    writes: list[dict[str, str]] = []

    monkeypatch.setattr(
        chat_router,
        "_verify_provider_configuration",
        lambda pending_config: 12,
    )
    monkeypatch.setattr(
        chat_router, "_write_env_values", lambda updates: writes.append(updates)
    )

    admin = await _register_user(client, "admin@example.com", display_name="Admin")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {admin['session_token']}"}

    llm_response = await client.post(
        "/chat/llm/provider-config",
        json={
            "provider": "deepseek",
            "api_key": "admin-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "thinking_mode": "off",
        },
        headers=headers,
    )
    web_search_response = await client.post(
        "/chat/web-search/config",
        json={
            "provider": "tavily",
            "tavily_api_key": "admin-tavily-key",
            "fallback_html": True,
            "tavily_search_depth": "basic",
        },
        headers=headers,
    )

    assert llm_response.status_code == 200
    assert web_search_response.status_code == 200
    assert any(update.get("DEEPSEEK_API_KEY") == "admin-key" for update in writes)
    assert any(update.get("TAVILY_API_KEY") == "admin-tavily-key" for update in writes)
