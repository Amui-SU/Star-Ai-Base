import pytest
from langchain.schema import Document


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
    display_name: str = "Chat User",
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


async def _create_knowledge_base(client, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": "Credential KB"},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _patch_scoped_documents(monkeypatch):
    async def fake_loader(*_args, **_kwargs):
        return [
            Document(
                page_content="知识库里的一段资料",
                metadata={
                    "bvid": "BV1",
                    "title": "测试视频",
                    "url": "https://www.bilibili.com/video/BV1",
                },
            )
        ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases._load_scoped_chat_documents",
        fake_loader,
    )


def _patch_fake_llm(monkeypatch, captured_config: dict):
    class _FakeCompletions:
        def create(self, **_kwargs):
            message = type(
                "Message",
                (),
                {"content": "## 回答\n- 使用用户账号", "reasoning_content": None},
            )()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    def fake_get_llm_client(config):
        captured_config.update(config)
        return _FakeClient()

    monkeypatch.setattr("app.routers.chat._get_llm_client", fake_get_llm_client)


def _configure_official_deepseek(monkeypatch):
    from app.routers import chat

    monkeypatch.setattr(chat.settings, "deepseek_api_key", "sk-official-secret")
    monkeypatch.setattr(
        chat.settings, "deepseek_base_url", "https://api.deepseek.com/v1"
    )
    monkeypatch.setattr(chat.settings, "deepseek_model", "deepseek-chat")
    monkeypatch.setattr(chat, "_current_llm_provider", "deepseek")


@pytest.mark.asyncio
async def test_scoped_chat_requires_user_api_account(client, monkeypatch):
    auth = await _register_user(client, "missing-api-account@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    knowledge_base = await _create_knowledge_base(client, headers)
    source = await client.post(
        "/chat/llm/source",
        json={"api_source": "personal"},
        headers=headers,
    )
    assert source.status_code == 200
    _patch_scoped_documents(monkeypatch)
    captured_config: dict = {}
    _patch_fake_llm(monkeypatch, captured_config)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "请回答"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "api_account_required",
        "message": "请先添加个人 AI 服务密钥，或切换到官方通道。",
    }
    assert captured_config == {}


@pytest.mark.asyncio
async def test_model_config_reflects_current_user_api_accounts(client):
    auth = await _register_user(client, "model-config-user@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "sk-user-secret",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=headers,
    )
    assert created.status_code == 200

    response = await client.get("/chat/llm/config", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_provider"] == "deepseek"
    provider = next(
        item for item in payload["providers"] if item["provider"] == "deepseek"
    )
    assert provider["enabled"] is True
    assert provider["model"] == "deepseek-chat"
    assert "sk-user-secret" not in str(payload)


@pytest.mark.asyncio
async def test_model_config_exposes_official_and_personal_sources(client, monkeypatch):
    _configure_official_deepseek(monkeypatch)
    auth = await _register_user(client, "source-config-user@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    response = await client.get("/chat/llm/config", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_api_source"] == "official"
    provider = next(
        item for item in payload["providers"] if item["provider"] == "deepseek"
    )
    assert provider["enabled"] is True
    assert provider["official_enabled"] is True
    assert provider["personal_enabled"] is False
    assert "sk-official-secret" not in str(payload)


@pytest.mark.asyncio
async def test_user_can_switch_between_official_and_personal_sources(
    client, monkeypatch
):
    _configure_official_deepseek(monkeypatch)
    auth = await _register_user(client, "source-switch-user@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    created = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "sk-user-secret",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=headers,
    )
    assert created.status_code == 200

    official = await client.post(
        "/chat/llm/source",
        json={"api_source": "official"},
        headers=headers,
    )
    personal = await client.post(
        "/chat/llm/source",
        json={"api_source": "personal"},
        headers=headers,
    )

    assert official.status_code == 200
    assert official.json()["current_api_source"] == "official"
    assert personal.status_code == 200
    assert personal.json()["current_api_source"] == "personal"


@pytest.mark.asyncio
async def test_web_search_config_reflects_current_user_tavily_account(
    client,
    monkeypatch,
):
    from app.routers import chat

    monkeypatch.setattr(chat.settings, "tavily_api_key", "")
    auth = await _register_user(client, "tavily-config-user@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    created = await client.post(
        "/api-accounts",
        json={
            "provider": "tavily",
            "api_key": "tvly-user-secret",
        },
        headers=headers,
    )
    assert created.status_code == 200

    response = await client.get("/chat/web-search/config", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tavily_configured"] is True
    assert "tvly-user-secret" not in str(payload)


@pytest.mark.asyncio
async def test_scoped_chat_uses_current_user_api_account(client, monkeypatch):
    auth = await _register_user(client, "chat-api-account@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    knowledge_base = await _create_knowledge_base(client, headers)
    account = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "sk-user-secret",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers=headers,
    )
    assert account.status_code == 200
    _patch_scoped_documents(monkeypatch)
    captured_config: dict = {}
    _patch_fake_llm(monkeypatch, captured_config)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "请回答"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "## 回答\n- 使用用户账号"
    assert captured_config["api_key"] == "sk-user-secret"
    assert captured_config["provider"] == "deepseek"
    assert captured_config["model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_scoped_chat_uses_official_source_when_selected(client, monkeypatch):
    _configure_official_deepseek(monkeypatch)
    auth = await _register_user(client, "official-chat-source@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    knowledge_base = await _create_knowledge_base(client, headers)
    source = await client.post(
        "/chat/llm/source",
        json={"api_source": "official"},
        headers=headers,
    )
    assert source.status_code == 200
    _patch_scoped_documents(monkeypatch)
    captured_config: dict = {}
    _patch_fake_llm(monkeypatch, captured_config)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "请回答"},
        headers=headers,
    )

    assert response.status_code == 200
    assert captured_config["api_source"] == "official"
    assert captured_config["api_key"] == "sk-official-secret"
    assert captured_config["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_personal_source_never_falls_back_to_official_key(client, monkeypatch):
    _configure_official_deepseek(monkeypatch)
    auth = await _register_user(client, "personal-no-fallback@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    knowledge_base = await _create_knowledge_base(client, headers)
    source = await client.post(
        "/chat/llm/source",
        json={"api_source": "personal"},
        headers=headers,
    )
    assert source.status_code == 200
    assert source.json()["current_api_source"] == "personal"
    _patch_scoped_documents(monkeypatch)
    captured_config: dict = {}
    _patch_fake_llm(monkeypatch, captured_config)

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "请回答"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "api_account_required"
    assert captured_config == {}


@pytest.mark.asyncio
async def test_personal_source_health_does_not_probe_official_key(client, monkeypatch):
    _configure_official_deepseek(monkeypatch)
    auth = await _register_user(client, "personal-health-no-fallback@example.com")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    source = await client.post(
        "/chat/llm/source",
        json={"api_source": "personal"},
        headers=headers,
    )
    assert source.status_code == 200

    def fail_if_called(_config):
        raise AssertionError("personal source should not probe official config")

    monkeypatch.setattr("app.routers.chat._get_llm_client", fail_if_called)

    response = await client.get("/chat/health/llm", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "down"
    assert "个人 AI 服务密钥" in payload["message"]
