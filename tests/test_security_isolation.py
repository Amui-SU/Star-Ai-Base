import pytest

from app.models import VideoCache


async def _register_user(client, email: str = "secure@example.com") -> dict:
    code_resp = await client.post("/system-auth/send-code", json={"email": email})
    assert code_resp.status_code == 200
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Secure User",
            "code": code_resp.json()["code"],
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_llm_management_endpoints_require_login(client):
    endpoints = [
        ("GET", "/chat/llm/config", None),
        ("POST", "/chat/llm/config", {"provider": "dashscope"}),
        (
            "POST",
            "/chat/llm/provider-config",
            {"provider": "dashscope", "api_key": "key", "thinking_mode": "off"},
        ),
        ("GET", "/chat/health/llm", None),
    ]

    for method, path, payload in endpoints:
        response = await client.request(method, path, json=payload)
        assert response.status_code == 401, path


@pytest.mark.asyncio
async def test_authenticated_user_can_read_and_save_llm_config(client, monkeypatch):
    await _register_user(client, "llm-owner@example.com")
    captured = {}

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda provider=None: {
            "provider": provider or "deepseek",
            "provider_label": "DeepSeek",
            "api_key": "saved-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr(
        "app.routers.chat._verify_provider_configuration",
        lambda config: captured.setdefault("verified_config", config) and 88,
    )
    monkeypatch.setattr(
        "app.routers.chat._write_env_values",
        lambda updates: captured.setdefault("updates", updates),
    )

    config_response = await client.get("/chat/llm/config")
    assert config_response.status_code == 200

    save_response = await client.post(
        "/chat/llm/provider-config",
        json={
            "provider": "deepseek",
            "api_key": "new-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "thinking_mode": "off",
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["latency_ms"] == 88
    assert captured["verified_config"]["api_key"] == "new-key"
    assert captured["updates"]["DEEPSEEK_API_KEY"] == "new-key"


@pytest.mark.asyncio
async def test_legacy_global_knowledge_and_chat_endpoints_return_410(client):
    endpoints = [
        ("GET", "/knowledge/stats", None),
        ("GET", "/knowledge/folders/status?session_id=legacy", None),
        ("POST", "/knowledge/folders/sync?session_id=legacy", {"folder_ids": [1]}),
        ("POST", "/knowledge/build?session_id=legacy", {"folder_ids": [1]}),
        ("DELETE", "/knowledge/clear", None),
        ("DELETE", "/knowledge/video/BV1legacy01", None),
        ("POST", "/chat/ask", {"question": "hello"}),
        ("POST", "/chat/ask/stream", {"question": "hello"}),
        ("POST", "/chat/search?query=hello", None),
    ]

    for method, path, payload in endpoints:
        response = await client.request(method, path, json=payload)
        assert response.status_code == 410, path
        assert "/knowledge-bases" in response.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_global_endpoints_return_410_without_legacy_inputs(client):
    endpoints = [
        ("GET", "/knowledge/folders/status"),
        ("POST", "/knowledge/folders/sync"),
        ("POST", "/knowledge/build"),
        ("POST", "/chat/ask"),
        ("POST", "/chat/ask/stream"),
        ("POST", "/chat/search"),
    ]

    for method, path in endpoints:
        response = await client.request(method, path)
        assert response.status_code == 410, path
        assert "/knowledge-bases" in response.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_auth_and_favorites_endpoints_return_410(client):
    endpoints = [
        ("GET", "/auth/qrcode"),
        ("GET", "/auth/qrcode/poll/legacy-key"),
        ("GET", "/auth/session/legacy-session"),
        ("DELETE", "/auth/session/legacy-session"),
        ("GET", "/favorites/list?session_id=legacy"),
        ("GET", "/favorites/123/videos?session_id=legacy"),
        ("GET", "/favorites/123/all-videos?session_id=legacy"),
        ("POST", "/favorites/organize/preview?session_id=legacy"),
        ("POST", "/favorites/organize/execute?session_id=legacy"),
        ("POST", "/favorites/organize/clean-invalid?session_id=legacy"),
    ]

    for method, path in endpoints:
        response = await client.request(method, path)
        assert response.status_code == 410, path
        assert "/source-bindings" in response.json()["detail"]


@pytest.mark.asyncio
async def test_video_cache_allows_same_bvid_in_distinct_knowledge_bases(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add_all(
            [
                VideoCache(
                    bvid="BV1shared",
                    title="Workspace 1 title",
                    content="workspace 1 content",
                    is_processed=True,
                    workspace_id=1,
                    knowledge_base_id=10,
                    source_binding_id=None,
                ),
                VideoCache(
                    bvid="BV1shared",
                    title="Workspace 2 title",
                    content="workspace 2 content",
                    is_processed=True,
                    workspace_id=2,
                    knowledge_base_id=20,
                    source_binding_id=None,
                ),
            ]
        )
        await session.commit()

        rows = (
            (
                await session.execute(
                    VideoCache.__table__.select()
                    .where(VideoCache.bvid == "BV1shared")
                    .order_by(VideoCache.workspace_id)
                )
            )
            .mappings()
            .all()
        )

    assert [row["title"] for row in rows] == ["Workspace 1 title", "Workspace 2 title"]


def test_scoped_vector_delete_filters_by_workspace_knowledge_base_and_bvid():
    from app.services.rag import RAGService

    captured = {}

    class FakeCollection:
        def delete(self, where=None):
            captured["where"] = where

    service = RAGService.__new__(RAGService)
    service.vectorstore = type("VectorStore", (), {"_collection": FakeCollection()})()

    service.delete_video_in_knowledge_base(
        workspace_id=1,
        knowledge_base_id=10,
        bvid="BV1shared",
    )

    assert captured["where"] == {
        "$and": [
            {"workspace_id": 1},
            {"knowledge_base_id": 10},
            {"bvid": "BV1shared"},
        ]
    }
