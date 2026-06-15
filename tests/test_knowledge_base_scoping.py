import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import (
    ContentSource,
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    SourceBinding,
    SourceCredential,
    SystemSession,
    VideoContent,
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
    return response.json()


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


@pytest.mark.asyncio
async def test_scoped_chat_stream_requires_owned_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice Stream KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.post(
        f"/knowledge-bases/{alice_kb['id']}/chat/stream",
        json={"question": "hello"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_chat_stream_returns_answer_for_owner(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Owner Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "Streamed answer chunk.",
                        "metadata": {
                            "bvid": "BV1st411c7mD",
                            "title": "Stream Intro",
                            "url": "https://www.bilibili.com/video/BV1st411c7mD",
                        },
                    },
                )()
            ]

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "stream please"},
    )

    assert response.status_code == 200
    assert "Streamed answer chunk." in response.text
    assert "[[SOURCES_JSON]]" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_json_encodes_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Thinking Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "context",
                        "metadata": {"bvid": "BV1", "title": "Source"},
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        yield "thinking", "思考"
        yield "answer", "done"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "show thinking"},
    )

    assert response.status_code == 200
    assert '[[THINKING_JSON]]"思考"' in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_configured_thinking(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Native Thinking KB")
    captured = {}

    class FakeRAGService:
        def search_in_knowledge_base(self, *args, **kwargs):
            return [
                type(
                    "FakeDocument",
                    (),
                    {
                        "page_content": "知识库上下文",
                        "metadata": {
                            "bvid": "BV1thinking",
                            "title": "Thinking Source",
                            "url": "https://www.bilibili.com/video/BV1thinking",
                        },
                    },
                )()
            ]

    def fake_stream_llm_events(messages):
        captured["messages"] = messages
        yield "thinking", "先分析"
        yield "answer", "模型答案"

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._stream_llm_events",
        fake_stream_llm_events,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._resolve_llm_config",
        lambda: {
            "thinking_config": {"thinking": {"type": "enabled"}},
        },
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "请回答"},
    )

    assert response.status_code == 200
    assert "知识库上下文" in str(captured["messages"])
    assert "原生 reasoning/thinking" in str(captured["messages"])
    assert '[[THINKING_DELTA]]"先分析"' in response.text
    assert "模型答案" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_stream_emits_empty_sources_trailer(client, monkeypatch):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Stream KB")

    class FakeRAGService:
        def search_in_knowledge_base(
            self,
            query,
            workspace_id,
            knowledge_base_id,
            k=5,
            bvids=None,
        ):
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "nothing here"},
    )

    assert response.status_code == 200
    assert "[[SOURCES_JSON]][]" in response.text


@pytest.mark.asyncio
async def test_scoped_chat_unions_folder_and_explicit_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Chat KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1FOLDER", "Folder video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=20,
        title="Explicit video folder",
        videos=[("BV1EXPLICIT", "Explicit video")],
    )
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
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={
            "question": "scope this",
            "folder_ids": [10],
            "bvids": ["BV1EXPLICIT"],
        },
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1EXPLICIT", "BV1FOLDER"]


@pytest.mark.asyncio
async def test_scoped_search_passes_resolved_video_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Search KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1SEARCH", "Search video")],
    )
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
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/search",
        json={"query": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1SEARCH"]


@pytest.mark.asyncio
async def test_scoped_chat_stream_uses_same_resolved_scope(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Scoped Stream KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Selected folder",
        videos=[("BV1STREAM", "Stream video")],
    )
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
            captured["bvids"] = bvids
            return []

    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: FakeRAGService(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat/stream",
        json={"question": "scope this", "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["bvids"] == ["BV1STREAM"]


@pytest.mark.asyncio
async def test_scoped_chat_rejects_external_bvid(
    client,
    db_session_factory,
    monkeypatch,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/chat",
        json={"question": "scope this", "bvids": ["BV2EXTERNAL"]},
    )

    assert response.status_code == 400
    assert "BV2EXTERNAL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scope_options_only_returns_current_knowledge_base(
    client,
    db_session_factory,
):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Alice KB")
    other_knowledge_base = await create_knowledge_base(client, "Other KB")
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=knowledge_base,
        media_id=10,
        title="Current folder",
        videos=[("BV1CURRENT", "Current video")],
    )
    await seed_scope_folder(
        db_session_factory,
        knowledge_base=other_knowledge_base,
        media_id=20,
        title="External folder",
        videos=[("BV2EXTERNAL", "External video")],
    )

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/scope-options"
    )

    assert response.status_code == 200
    assert response.json() == {
        "folders": [
            {
                "media_id": 10,
                "title": "Current folder",
                "video_count": 1,
                "videos": [
                    {"bvid": "BV1CURRENT", "title": "Current video"},
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_scope_options_requires_login(client):
    response = await client.get("/knowledge-bases/1/scope-options")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scope_options_hides_other_users_knowledge_base(client):
    await register_user(client, "alice@example.com", "Alice")
    alice_kb = await create_knowledge_base(client, "Alice KB")
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    response = await client.get(f"/knowledge-bases/{alice_kb['id']}/scope-options")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_rejects_unknown_source_binding(client):
    await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build KB")

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": 999, "folder_ids": [1]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoped_build_records_scope_metadata(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    async def fake_run_scoped_build(**_kwargs):
        pass

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Build Metadata KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [1, 2]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["workspace_id"] == knowledge_base["workspace_id"]
    assert body["knowledge_base_id"] == knowledge_base["id"]
    assert body["source_binding_id"] == binding.id
    assert body["task_id"]


@pytest.mark.asyncio
async def test_scoped_build_accepts_single_video_selection(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "video-build@example.com", "Video Build")
    knowledge_base = await create_knowledge_base(client, "Video Build KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={
            "source_binding_id": binding.id,
            "folder_ids": [],
            "video_folder_ids": [10],
            "bvids": ["BV1ONLY"],
        },
    )

    assert response.status_code == 200
    assert captured["folder_ids"] == []
    assert captured["video_folder_ids"] == [10]
    assert captured["include_bvids"] == {"BV1ONLY"}


@pytest.mark.asyncio
async def test_scoped_build_starts_when_vector_service_is_unavailable(
    client,
    db_session_factory,
    monkeypatch,
):
    class FakeBilibiliService:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    captured = {}

    async def fake_run_scoped_build(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.knowledge_bases.BilibiliService",
        FakeBilibiliService,
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ASRService",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.ContentFetcher",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases.get_rag_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing embedding key")),
    )
    monkeypatch.setattr(
        "app.routers.knowledge_bases._run_scoped_build",
        fake_run_scoped_build,
    )

    auth = await register_user(client, "no-vector-build@example.com", "No Vector")
    knowledge_base = await create_knowledge_base(client, "No Vector KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": [10]},
    )

    assert response.status_code == 200
    assert captured["rag"].add_video_content(object()) == 0


@pytest.mark.asyncio
async def test_partial_folder_sync_keeps_existing_unselected_videos(
    db_session_factory,
):
    from app.routers.knowledge import _sync_folder

    class FakeBilibili:
        async def get_favorite_content(self, folder_id, pn=1, ps=1):
            return {"info": {"title": "Folder A", "media_count": 2}}

        async def get_all_favorite_videos(self, folder_id):
            return [
                {"bvid": "BV1ONLY", "title": "Video one", "attr": 0},
                {"bvid": "BV1SKIP", "title": "Video two", "attr": 0},
            ]

    class FakeContentFetcher:
        async def fetch_content(self, bvid, cid=None, title=None):
            return VideoContent(
                bvid=bvid,
                title=title or bvid,
                content="selected video content " * 5,
                source=ContentSource.BASIC_INFO,
            )

    class FakeRag:
        def delete_video(self, bvid):
            pass

        def add_video_content(self, *args, **kwargs):
            return 1

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="",
            media_id=10,
            title="Folder A",
            media_count=2,
            last_sync_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        session.add(FavoriteVideo(folder_id=folder.id, bvid="BV1OLD"))
        session.add(
            VideoCache(
                bvid="BV1OLD",
                title="Old video",
                content="old content " * 8,
                content_source=ContentSource.BASIC_INFO.value,
                is_processed=True,
            )
        )
        await session.commit()

        result = await _sync_folder(
            db=session,
            bili=FakeBilibili(),
            rag=FakeRag(),
            content_fetcher=FakeContentFetcher(),
            session_id="",
            folder_id=10,
            include_bvids={"BV1ONLY"},
        )

        rows = await session.execute(
            select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder.id)
        )

    assert result["removed"] == 0
    assert set(rows.scalars().all()) == {"BV1OLD", "BV1ONLY"}


@pytest.mark.asyncio
async def test_scoped_build_rejects_empty_folder_ids(client, db_session_factory):
    auth = await register_user(client, "alice@example.com", "Alice")
    knowledge_base = await create_knowledge_base(client, "Empty Folders KB")
    binding = await create_source_binding(
        db_session_factory,
        user_id=auth["user"]["id"],
        workspace_id=auth["workspace"]["id"],
    )

    response = await client.post(
        f"/knowledge-bases/{knowledge_base['id']}/build",
        json={"source_binding_id": binding.id, "folder_ids": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "folder_ids cannot be empty"


@pytest.mark.asyncio
async def test_scoped_build_rejects_other_users_source_binding(
    client,
    db_session_factory,
):
    alice_auth = await register_user(client, "alice@example.com", "Alice")
    alice_binding = await create_source_binding(
        db_session_factory,
        user_id=alice_auth["user"]["id"],
        workspace_id=alice_auth["workspace"]["id"],
    )
    await client.post("/system-auth/logout")

    await register_user(client, "bob@example.com", "Bob")
    bob_kb = await create_knowledge_base(client, "Bob Build KB")

    response = await client.post(
        f"/knowledge-bases/{bob_kb['id']}/build",
        json={"source_binding_id": alice_binding.id, "folder_ids": [1]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_build_status_polling_does_not_touch_session_last_seen(
    client,
    db_session_factory,
):
    auth = await register_user(client, "poll-status@example.com", "Poll Status")
    knowledge_base = await create_knowledge_base(client, "Poll Status KB")
    task_id = "poll-status-task"

    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        before = auth_session.last_seen_at
        session.add(
            IngestionTask(
                task_id=task_id,
                workspace_id=knowledge_base["workspace_id"],
                knowledge_base_id=knowledge_base["id"],
                source_binding_id=None,
                created_by=auth["user"]["id"],
                status="running",
                progress=42,
                current_step="polling",
            )
        )
        await session.commit()

    response = await client.get(
        f"/knowledge-bases/{knowledge_base['id']}/build/status/{task_id}"
    )

    assert response.status_code == 200
    assert response.json()["progress"] == 42
    async with db_session_factory() as session:
        auth_session = (
            (
                await session.execute(
                    select(SystemSession).where(
                        SystemSession.user_id == auth["user"]["id"]
                    )
                )
            )
            .scalars()
            .first()
        )
        assert auth_session.last_seen_at == before
