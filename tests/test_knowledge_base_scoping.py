import asyncio
import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    SourceBinding,
    SourceCredential,
    SystemSession,
    VideoCache,
)
from app.security import encrypt_text


async def _get_code(client, email: str) -> str:
    resp = await client.post("/system-auth/send-code", json={"email": email})
    assert resp.status_code == 200
    return resp.json()["code"]


async def register_user(client, email: str, display_name: str) -> dict:
    code = await _get_code(client, email)
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    auth = response.json()
    account_response = await client.post(
        "/api-accounts",
        json={
            "provider": "deepseek",
            "api_key": "test-user-api-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "is_default": True,
        },
        headers={"Authorization": f"Bearer {auth['session_token']}"},
    )
    assert account_response.status_code == 200
    return auth


async def create_knowledge_base(client, name: str = "Scoped KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "scope test"},
    )
    assert response.status_code == 200
    return response.json()


async def create_source_binding(
    db_session_factory,
    *,
    user_id: int,
    workspace_id: int,
    status: str = "active",
) -> SourceBinding:
    async with db_session_factory() as session:
        binding = SourceBinding(
            user_id=user_id,
            workspace_id=workspace_id,
            source_type="bilibili",
            external_account_id=f"mid-{user_id}-{workspace_id}-{status}",
            external_account_name="Bilibili Account",
            status=status,
        )
        session.add(binding)
        await session.flush()
        session.add(
            SourceCredential(
                user_id=user_id,
                source_binding_id=binding.id,
                encrypted_payload=encrypt_text(
                    json.dumps(
                        {
                            "SESSDATA": "test-session",
                            "bili_jct": "test-csrf",
                            "DedeUserID": str(user_id),
                        }
                    )
                ),
            )
        )
        await session.commit()
        await session.refresh(binding)
        return binding


async def seed_scope_folder(
    db_session_factory,
    *,
    knowledge_base: dict,
    media_id: int,
    title: str,
    videos: list[tuple[str, str]],
) -> None:
    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id=f"scope-{knowledge_base['id']}-{media_id}",
            workspace_id=knowledge_base["workspace_id"],
            knowledge_base_id=knowledge_base["id"],
            media_id=media_id,
            title=title,
            last_sync_at=datetime(2026, 6, 14),
            updated_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        for bvid, video_title in videos:
            session.add(
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid=bvid,
                    workspace_id=knowledge_base["workspace_id"],
                    knowledge_base_id=knowledge_base["id"],
                )
            )
            session.add(
                VideoCache(
                    bvid=bvid,
                    title=video_title,
                    is_processed=True,
                    workspace_id=knowledge_base["workspace_id"],
                    knowledge_base_id=knowledge_base["id"],
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_scoped_stats_requires_login(client):
    response = await client.get("/knowledge-bases/1/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scoped_stats_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/stats")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_search_uses_workspace_and_knowledge_base_filter(
    client,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Search KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            captured["bvids"] = bvids
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "chunk text",
                        "metadata": {
                            "bvid": "BV1xx411c7mD",
                            "title": "Test Video",
                            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "人工智能", "k": 3},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Test Video"
    assert captured == {
        "query": "人工智能",
        "workspace_id": knowledge_base["workspace_id"],
        "knowledge_base_id": knowledge_base["id"],
        "k": 3,
        "bvids": None,
    }


@pytest.mark.asyncio
async def test_scoped_chat_uses_scoped_retrieval(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Chat KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            captured["query"] = query
            captured["workspace_id"] = workspace_id
            captured["knowledge_base_id"] = knowledge_base_id
            captured["k"] = k
            captured["bvids"] = bvids
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Python is a programming language.",
                        "metadata": {
                            "bvid": "BV1py411c7mD",
                            "title": "Python Intro",
                            "url": "https://www.bilibili.com/video/BV1py411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "What is Python?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["answer"]
    assert body["sources"][0]["title"] == "Python Intro"
    assert captured["workspace_id"] == knowledge_base["workspace_id"]
    assert captured["knowledge_base_id"] == knowledge_base["id"]
