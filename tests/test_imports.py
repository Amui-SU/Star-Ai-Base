import os

import pytest
from sqlalchemy import select

from app.models import (
    ContentSource,
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    VideoCache,
)


async def _get_code(client, email: str) -> str:
    response = await client.post("/system-auth/send-code", json={"email": email})
    assert response.status_code == 200
    return response.json()["code"]


async def register_user(client, email: str, display_name: str = "Import User") -> dict:
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


async def create_knowledge_base(client, name: str = "Import KB") -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name, "description": "import test"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_local_video_import_creates_task_and_stores_upload(
    client,
    db_session_factory,
    monkeypatch,
    tmp_path,
):
    captured = {}

    async def fake_run_local_video_import(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.routers.imports._run_local_video_import",
        fake_run_local_video_import,
    )
    monkeypatch.setattr("app.routers.imports._LOCAL_IMPORT_DIR", tmp_path)

    auth = await register_user(client, "local-video-import@example.com")
    knowledge_base = await create_knowledge_base(client)

    response = await client.post(
        "/imports/local-video",
        data={
            "knowledge_base_id": str(knowledge_base["id"]),
            "title": "本地演示视频",
        },
        files={"file": ("demo.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "pending"
    assert body["source_type"] == "local_video"
    assert body["task_id"]
    assert body["bvid"].startswith("LV")

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(
                        IngestionTask.task_id == body["task_id"]
                    )
                )
            )
            .scalars()
            .one()
        )
        assert task.workspace_id == auth["workspace"]["id"]
        assert task.knowledge_base_id == knowledge_base["id"]
        assert task.source_binding_id is None
        assert task.total_items == 1

    assert captured["task_id"] == body["task_id"]
    assert captured["local_id"] == body["bvid"]
    assert captured["title"] == "本地演示视频"
    assert captured["workspace_id"] == auth["workspace"]["id"]
    assert captured["knowledge_base_id"] == knowledge_base["id"]
    assert os.path.exists(captured["file_path"])
    assert captured["file_path"].endswith(".mp4")


@pytest.mark.asyncio
async def test_local_video_import_requires_video_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.imports._LOCAL_IMPORT_DIR", tmp_path)
    await register_user(client, "local-video-type@example.com")
    knowledge_base = await create_knowledge_base(client)

    response = await client.post(
        "/imports/local-video",
        data={"knowledge_base_id": str(knowledge_base["id"])},
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请上传视频文件"


@pytest.mark.asyncio
async def test_local_video_import_task_writes_transcript_into_scope(
    db_session_factory,
    monkeypatch,
    tmp_path,
):
    import app.database as database
    from app.routers.imports import _run_local_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeASRService:
        async def transcribe_local_file(self, file_path):
            assert file_path.endswith("demo.mp4")
            return "本地视频转写内容 " * 20

    class FakeRAGService:
        def __init__(self):
            self.deleted = []
            self.added = []

        def delete_video_in_knowledge_base(self, **kwargs):
            self.deleted.append(kwargs)

        def add_video_content(self, content, **kwargs):
            self.added.append((content, kwargs))
            return 1

    rag = FakeRAGService()
    monkeypatch.setattr("app.routers.imports.ASRService", FakeASRService)
    monkeypatch.setattr("app.routers.imports.get_rag_service", lambda: rag)
    file_path = tmp_path / "demo.mp4"
    file_path.write_bytes(b"video bytes")

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="local-task",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                created_by=5,
                status="pending",
                total_items=1,
            )
        )
        await session.commit()

    await _run_local_video_import(
        task_id="local-task",
        local_id="LVLOCALVIDEO",
        title="本地视频",
        file_path=str(file_path),
        workspace_id=3,
        knowledge_base_id=9,
    )

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(IngestionTask.task_id == "local-task")
                )
            )
            .scalars()
            .one()
        )
        cache = (
            (
                await session.execute(
                    select(VideoCache).where(VideoCache.bvid == "LVLOCALVIDEO")
                )
            )
            .scalars()
            .one()
        )
        folder = (
            (
                await session.execute(
                    select(FavoriteFolder).where(
                        FavoriteFolder.knowledge_base_id == 9,
                        FavoriteFolder.media_id == 0,
                    )
                )
            )
            .scalars()
            .one()
        )
        favorite_video = (
            (
                await session.execute(
                    select(FavoriteVideo).where(
                        FavoriteVideo.folder_id == folder.id,
                        FavoriteVideo.bvid == "LVLOCALVIDEO",
                    )
                )
            )
            .scalars()
            .one()
        )

    assert task.status == "completed"
    assert task.progress == 100
    assert task.processed_items == 1
    assert cache.title == "本地视频"
    assert cache.content.startswith("本地视频转写内容")
    assert cache.content_source == ContentSource.ASR.value
    assert cache.workspace_id == 3
    assert cache.knowledge_base_id == 9
    assert folder.title == "单条视频导入"
    assert favorite_video.workspace_id == 3
    assert rag.deleted == [
        {
            "workspace_id": 3,
            "knowledge_base_id": 9,
            "bvid": "LVLOCALVIDEO",
        }
    ]
    added_content, metadata = rag.added[0]
    assert added_content.bvid == "LVLOCALVIDEO"
    assert metadata == {
        "workspace_id": 3,
        "knowledge_base_id": 9,
        "source_binding_id": None,
    }


@pytest.mark.asyncio
async def test_local_video_import_task_cleans_upload_when_transcription_fails(
    db_session_factory,
    monkeypatch,
    tmp_path,
):
    import app.database as database
    from app.routers.imports import _run_local_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeASRService:
        async def transcribe_local_file(self, file_path):
            assert os.path.exists(file_path)
            return None

    monkeypatch.setattr("app.routers.imports.ASRService", FakeASRService)
    monkeypatch.setattr("app.routers.imports.get_rag_service", lambda: object())
    file_path = tmp_path / "failed.mp4"
    file_path.write_bytes(b"video bytes")

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="failed-local-task",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                created_by=5,
                status="pending",
                total_items=1,
            )
        )
        await session.commit()

    await _run_local_video_import(
        task_id="failed-local-task",
        local_id="LVFAILEDLOCAL",
        title="本地视频",
        file_path=str(file_path),
        workspace_id=3,
        knowledge_base_id=9,
    )

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(
                        IngestionTask.task_id == "failed-local-task"
                    )
                )
            )
            .scalars()
            .one()
        )

    assert not file_path.exists()
    assert task.status == "failed"
