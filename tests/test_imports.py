import os

import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    VideoCache,
)
from app.schemas.content import ContentSource


def test_import_vector_delete_failure_is_logged(monkeypatch):
    from app.routers.imports import _delete_existing_import_vectors

    warnings = []

    class FailingRAGService:
        def delete_video_in_knowledge_base(self, **kwargs):
            raise RuntimeError("vector store is locked")

    monkeypatch.setattr(
        "app.routers.imports.logger.warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    _delete_existing_import_vectors(
        FailingRAGService(),
        workspace_id=3,
        knowledge_base_id=9,
        bvid="BVDELETEFAIL",
    )

    assert warnings
    assert "BVDELETEFAIL" in warnings[0]
    assert "vector" in warnings[0].lower()


@pytest.mark.asyncio
async def test_local_video_import_logs_cleanup_failure(
    db_session_factory,
    monkeypatch,
    tmp_path,
):
    import app.database as database
    from app.routers.imports import _run_local_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)
    warnings = []

    class FakeASRService:
        async def transcribe_local_file(self, file_path):
            return None

    monkeypatch.setattr("app.routers.imports.ASRService", FakeASRService)
    monkeypatch.setattr("app.routers.imports.get_rag_service", lambda: object())
    monkeypatch.setattr(
        "app.routers.imports.logger.warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    def fail_unlink(self):
        raise PermissionError("file is locked")

    monkeypatch.setattr("app.routers.imports.Path.unlink", fail_unlink)
    file_path = tmp_path / "locked.mp4"
    file_path.write_bytes(b"video bytes")

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="cleanup-failure-task",
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
        task_id="cleanup-failure-task",
        local_id="LVCLEANUPFAIL",
        title="Local Video",
        file_path=str(file_path),
        workspace_id=3,
        knowledge_base_id=9,
    )

    assert any("cleanup" in warning.lower() for warning in warnings)


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
    assert cache.cid is None
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
async def test_bilibili_video_import_task_persists_cid_for_timestamp_generation(
    db_session_factory,
    monkeypatch,
):
    import app.database as database
    from app.services.import_tasks import run_bilibili_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeBilibiliService:
        async def get_video_info(self, bvid):
            assert bvid == "BVCIDIMPORT"
            return {
                "cid": 456,
                "title": "B 站导入视频",
                "desc": "视频简介",
                "owner": {"name": "UP 主", "mid": 9},
                "duration": 360,
                "pic": "https://example.test/cover.jpg",
            }

        async def close(self):
            pass

    class FakeASRService:
        pass

    class FakeContentFetcher:
        def __init__(self, bili, asr):
            pass

        async def fetch_content(self, bvid, cid=None, title=None):
            from app.schemas.content import VideoContent

            assert (bvid, cid, title) == ("BVCIDIMPORT", 456, "B 站导入视频")
            return VideoContent(
                bvid=bvid,
                title=title,
                content="B 站视频字幕内容 " * 8,
                source=ContentSource.SUBTITLE,
                outline=[],
            )

    class FakeRAGService:
        def delete_video_in_knowledge_base(self, **kwargs):
            pass

        def add_video_content(self, content, **kwargs):
            return 1

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="bili-cid-task",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                created_by=5,
                status="pending",
                total_items=1,
            )
        )
        await session.commit()

    await run_bilibili_video_import(
        task_id="bili-cid-task",
        bvid="BVCIDIMPORT",
        workspace_id=3,
        knowledge_base_id=9,
        bilibili_service_class=FakeBilibiliService,
        asr_service_class=FakeASRService,
        content_fetcher_class=FakeContentFetcher,
        rag_factory=lambda: FakeRAGService(),
    )

    async with db_session_factory() as session:
        cache = (
            (
                await session.execute(
                    select(VideoCache).where(VideoCache.bvid == "BVCIDIMPORT")
                )
            )
            .scalars()
            .one()
        )

    assert cache.cid == 456


@pytest.mark.asyncio
async def test_bilibili_multi_part_import_uses_part_duration_for_timestamps(
    db_session_factory,
    monkeypatch,
):
    import app.database as database
    from app.services.import_tasks import run_bilibili_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeBilibiliService:
        async def get_video_info(self, bvid):
            assert bvid == "BVPARTIMPORT"
            return {
                "cid": 111,
                "title": "合集视频",
                "desc": "视频简介",
                "owner": {"name": "UP 主", "mid": 9},
                "duration": 3600,
                "pic": "https://example.test/cover.jpg",
            }

        async def close(self):
            pass

    class FakeASRService:
        pass

    class FakeContentFetcher:
        def __init__(self, bili, asr):
            pass

        async def fetch_content(self, bvid, cid=None, title=None):
            from app.schemas.content import VideoContent

            assert (bvid, cid, title) == ("BVPARTIMPORT", 222, "合集视频")
            return VideoContent(
                bvid=bvid,
                title=title,
                content="分 P 字幕内容 " * 8,
                source=ContentSource.SUBTITLE,
                outline=[],
            )

    class FakeRAGService:
        def delete_video_in_knowledge_base(self, **kwargs):
            pass

        def add_video_content(self, content, **kwargs):
            return 1

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="bili-part-duration-task",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                created_by=5,
                status="pending",
                total_items=1,
            )
        )
        await session.commit()

    await run_bilibili_video_import(
        task_id="bili-part-duration-task",
        bvid="BVPARTIMPORT",
        workspace_id=3,
        knowledge_base_id=9,
        cid=222,
        page_number=2,
        part_title="第二讲",
        total_parts=4,
        part_duration=540,
        bilibili_service_class=FakeBilibiliService,
        asr_service_class=FakeASRService,
        content_fetcher_class=FakeContentFetcher,
        rag_factory=lambda: FakeRAGService(),
    )

    async with db_session_factory() as session:
        cache = (
            (
                await session.execute(
                    select(VideoCache).where(VideoCache.bvid == "BVPARTIMPORT")
                )
            )
            .scalars()
            .one()
        )

    assert cache.cid == 222
    assert cache.page_number == 2
    assert cache.total_parts == 4
    assert cache.duration == 540


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
