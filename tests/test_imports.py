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

        async def fetch_content(self, bvid, cid=None, title=None, video_info=None):
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

        async def fetch_content(self, bvid, cid=None, title=None, video_info=None):
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


# ---------------------------------------------------------------------------
# 分P导入端点与分P数据隔离


class _FakeMultiPartBili:
    async def get_video_info(self, bvid):
        return {
            "bvid": bvid,
            "cid": 111,
            "title": "教程合集",
            "desc": "合集简介",
            "owner": {"name": "UP 主", "mid": 9},
            "duration": 900,
            "pic": "https://example.test/cover.jpg",
            "videos": 2,
            "pages": [
                {"cid": 111, "page": 1, "part": "第一讲", "duration": 400},
                {"cid": 222, "page": 2, "part": "第二讲", "duration": 500},
            ],
        }

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_detect_multi_part_endpoint_returns_pages(client, monkeypatch):
    monkeypatch.setattr("app.routers.imports.BilibiliService", _FakeMultiPartBili)
    await register_user(client, "detect-multi-part@example.com")

    response = await client.post(
        "/imports/detect-multi-part",
        json={"url": "https://www.bilibili.com/video/BV1Multi0001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    info = body["multi_part_info"]
    assert info["is_multi_part"] is True
    assert info["total_parts"] == 2
    assert [page["page"] for page in info["pages"]] == [1, 2]
    assert [page["cid"] for page in info["pages"]] == [111, 222]


@pytest.mark.asyncio
async def test_import_multi_part_endpoint_creates_one_task_per_part(
    client,
    db_session_factory,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.imports.BilibiliService", _FakeMultiPartBili)
    scheduled = []

    async def fake_run_batch(jobs, bvid, workspace_id, knowledge_base_id, video_info):
        scheduled.append(
            {
                "jobs": jobs,
                "bvid": bvid,
                "workspace_id": workspace_id,
                "knowledge_base_id": knowledge_base_id,
                "video_info": video_info,
            }
        )

    monkeypatch.setattr(
        "app.routers.imports._run_multi_part_batch",
        fake_run_batch,
    )

    await register_user(client, "multi-part-import@example.com")
    knowledge_base = await create_knowledge_base(client)

    response = await client.post(
        "/imports/multi-part",
        json={
            "url": "https://www.bilibili.com/video/BV1Multi0001",
            "knowledge_base_id": knowledge_base["id"],
            "page_indices": [1, 2],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["total_selected"] == 2
    assert len(body["task_ids"]) == 2

    async with db_session_factory() as session:
        tasks = (
            (
                await session.execute(
                    select(IngestionTask).where(
                        IngestionTask.task_id.in_(body["task_ids"])
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(tasks) == 2
    assert {task.knowledge_base_id for task in tasks} == {knowledge_base["id"]}

    # 整批分P调度为一个后台任务，video_info 直接透传不再重复请求
    assert len(scheduled) == 1
    batch = scheduled[0]
    assert batch["bvid"] == "BV1Multi0001"
    assert batch["knowledge_base_id"] == knowledge_base["id"]
    assert batch["video_info"]["title"] == "教程合集"
    first, second = batch["jobs"]
    assert (first["cid"], second["cid"]) == (111, 222)
    assert first["storage_bvid"] == "BV1Multi0001_p1"
    assert second["storage_bvid"] == "BV1Multi0001_p2"
    assert "P1/2" in first["title"] and "第一讲" in first["title"]
    assert "P2/2" in second["title"] and "第二讲" in second["title"]


@pytest.mark.asyncio
async def test_import_multi_part_endpoint_rejects_missing_knowledge_base(
    client,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.imports.BilibiliService", _FakeMultiPartBili)
    await register_user(client, "multi-part-no-kb@example.com")

    response = await client.post(
        "/imports/multi-part",
        json={
            "url": "https://www.bilibili.com/video/BV1Multi0001",
            "knowledge_base_id": 987654,
            "page_indices": [1],
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_multi_part_imports_keep_each_part_cached_and_indexed(
    db_session_factory,
    monkeypatch,
):
    import app.database as database
    from app.services.import_tasks import run_bilibili_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeBili:
        async def get_video_info(self, bvid):
            assert bvid == "BVPARTS"
            return {
                "cid": 111,
                "title": "教程合集",
                "desc": "合集简介",
                "owner": {"name": "UP 主", "mid": 9},
                "duration": 900,
                "pic": "https://example.test/cover.jpg",
            }

        async def close(self):
            pass

    class FakeASR:
        pass

    class FakeFetcher:
        def __init__(self, bili, asr):
            pass

        async def fetch_content(self, bvid, cid=None, title=None, video_info=None):
            from app.schemas.content import VideoContent

            assert bvid == "BVPARTS"
            return VideoContent(
                bvid=bvid,
                title=title,
                content=f"分P内容 cid={cid} " * 8,
                source=ContentSource.SUBTITLE,
                outline=[],
            )

    deleted = []
    added = []

    class FakeRAG:
        def delete_video_in_knowledge_base(self, **kwargs):
            deleted.append(kwargs["bvid"])

        def add_video_content(self, content, **kwargs):
            added.append(content.bvid)
            return 1

    async with db_session_factory() as session:
        for task_id in ("part-task-1", "part-task-2"):
            session.add(
                IngestionTask(
                    task_id=task_id,
                    workspace_id=3,
                    knowledge_base_id=9,
                    source_binding_id=None,
                    created_by=5,
                    status="pending",
                    total_items=1,
                )
            )
        await session.commit()

    rag = FakeRAG()
    for task_id, cid, page, part, storage in (
        ("part-task-1", 111, 1, "第一讲", "BVPARTS_p1"),
        ("part-task-2", 222, 2, "第二讲", "BVPARTS_p2"),
    ):
        await run_bilibili_video_import(
            task_id=task_id,
            bvid="BVPARTS",
            workspace_id=3,
            knowledge_base_id=9,
            cid=cid,
            page_number=page,
            part_title=part,
            total_parts=2,
            part_duration=400,
            storage_bvid=storage,
            title_override=f"教程合集 P{page}/2: {part}",
            bilibili_service_class=FakeBili,
            asr_service_class=FakeASR,
            content_fetcher_class=FakeFetcher,
            rag_factory=lambda: rag,
        )

    async with db_session_factory() as session:
        caches = (
            (
                await session.execute(
                    select(VideoCache).where(
                        VideoCache.bvid.in_(["BVPARTS_p1", "BVPARTS_p2"])
                    )
                )
            )
            .scalars()
            .all()
        )
        favorites = (
            (
                await session.execute(
                    select(FavoriteVideo).where(
                        FavoriteVideo.bvid.in_(["BVPARTS_p1", "BVPARTS_p2"])
                    )
                )
            )
            .scalars()
            .all()
        )

    by_bvid = {cache.bvid: cache for cache in caches}
    assert set(by_bvid) == {"BVPARTS_p1", "BVPARTS_p2"}
    assert by_bvid["BVPARTS_p1"].cid == 111
    assert by_bvid["BVPARTS_p2"].cid == 222
    assert by_bvid["BVPARTS_p1"].title == "教程合集 P1/2: 第一讲"
    assert by_bvid["BVPARTS_p2"].title == "教程合集 P2/2: 第二讲"
    assert len(favorites) == 2
    # 向量删除只影响各自分P，后导入的分P不会误删先导入的分P
    assert deleted == ["BVPARTS_p1", "BVPARTS_p2"]
    assert added == ["BVPARTS_p1", "BVPARTS_p2"]


@pytest.mark.asyncio
async def test_bilibili_video_import_uses_provided_video_info(
    db_session_factory,
    monkeypatch,
):
    import app.database as database
    from app.services.import_tasks import run_bilibili_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)
    api_calls = []

    class FakeBili:
        async def get_video_info(self, bvid):
            api_calls.append(bvid)
            raise AssertionError("video_info 已透传，不应再请求 B 站")

        async def close(self):
            pass

    class FakeASR:
        pass

    class FakeFetcher:
        def __init__(self, bili, asr):
            pass

        async def fetch_content(self, bvid, cid=None, title=None, video_info=None):
            from app.schemas.content import VideoContent

            assert video_info is not None
            assert video_info["title"] == "透传标题"
            return VideoContent(
                bvid=bvid,
                title=title,
                content="字幕内容 " * 8,
                source=ContentSource.SUBTITLE,
                outline=[],
            )

    class FakeRAG:
        def delete_video_in_knowledge_base(self, **kwargs):
            pass

        def add_video_content(self, content, **kwargs):
            return 1

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="passthrough-task",
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
        task_id="passthrough-task",
        bvid="BVPASSTHRU01",
        workspace_id=3,
        knowledge_base_id=9,
        cid=111,
        video_info={
            "cid": 111,
            "title": "透传标题",
            "desc": "",
            "owner": {},
            "duration": 100,
            "pic": "",
        },
        bilibili_service_class=FakeBili,
        asr_service_class=FakeASR,
        content_fetcher_class=FakeFetcher,
        rag_factory=lambda: FakeRAG(),
    )

    assert api_calls == []
    async with db_session_factory() as session:
        cache = (
            (
                await session.execute(
                    select(VideoCache).where(VideoCache.bvid == "BVPASSTHRU01")
                )
            )
            .scalars()
            .one()
        )
    assert cache.title == "透传标题"


@pytest.mark.asyncio
async def test_bilibili_video_import_reuses_cached_transcript(
    db_session_factory,
    monkeypatch,
):
    import app.database as database
    from app.services.import_tasks import run_bilibili_video_import

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    class FakeBili:
        async def get_video_info(self, bvid):
            raise AssertionError("命中缓存时不应请求 B 站")

        async def close(self):
            pass

    class FakeASR:
        pass

    class FakeFetcher:
        def __init__(self, bili, asr):
            pass

        async def fetch_content(self, bvid, cid=None, title=None, video_info=None):
            raise AssertionError("命中缓存时不应重新抓取/转写")

    added = []

    class FakeRAG:
        def delete_video_in_knowledge_base(self, **kwargs):
            pass

        def add_video_content(self, content, **kwargs):
            added.append(content)
            return 1

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="reuse-cache-task",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                created_by=5,
                status="pending",
                total_items=1,
            )
        )
        session.add(
            VideoCache(
                bvid="BVREUSE00001",
                title="已缓存视频",
                workspace_id=3,
                knowledge_base_id=9,
                source_binding_id=None,
                content="已有 ASR 转写内容 " * 10,
                content_source=ContentSource.ASR.value,
                is_processed=True,
            )
        )
        await session.commit()

    await run_bilibili_video_import(
        task_id="reuse-cache-task",
        bvid="BVREUSE00001",
        workspace_id=3,
        knowledge_base_id=9,
        bilibili_service_class=FakeBili,
        asr_service_class=FakeASR,
        content_fetcher_class=FakeFetcher,
        rag_factory=lambda: FakeRAG(),
    )

    assert len(added) == 1
    assert added[0].bvid == "BVREUSE00001"
    assert "已有 ASR 转写内容" in added[0].content

    async with db_session_factory() as session:
        task = (
            (
                await session.execute(
                    select(IngestionTask).where(
                        IngestionTask.task_id == "reuse-cache-task"
                    )
                )
            )
            .scalars()
            .one()
        )
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_run_multi_part_video_imports_limits_concurrency():
    import asyncio

    from app.services.import_tasks import run_multi_part_video_imports

    running = 0
    peak = 0
    finished = []

    async def fake_run_import(**kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        finished.append(kwargs["task_id"])

    jobs = [
        {
            "task_id": f"task-{index}",
            "cid": index,
            "page": index,
            "part": f"P{index}",
            "total_parts": 5,
            "duration": 100,
            "storage_bvid": f"BVBATCH00001_p{index}",
            "title": f"合集 P{index}/5",
        }
        for index in range(1, 6)
    ]

    await run_multi_part_video_imports(
        jobs,
        bvid="BVBATCH00001",
        workspace_id=3,
        knowledge_base_id=9,
        video_info={"title": "合集"},
        concurrency=2,
        run_import=fake_run_import,
    )

    assert sorted(finished) == [f"task-{index}" for index in range(1, 6)]
    assert peak <= 2


@pytest.mark.asyncio
async def test_import_task_status_endpoint(client, db_session_factory):
    auth = await register_user(client, "task-status@example.com")

    async with db_session_factory() as session:
        session.add(
            IngestionTask(
                task_id="status-task-1",
                workspace_id=auth["workspace"]["id"],
                knowledge_base_id=1,
                source_binding_id=None,
                created_by=auth["user"]["id"],
                status="running",
                progress=36,
                current_step="提取视频内容...",
                total_items=1,
            )
        )
        await session.commit()

    response = await client.get("/imports/tasks/status-task-1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["progress"] == 36
    assert body["current_step"] == "提取视频内容..."

    missing = await client.get("/imports/tasks/unknown-task")
    assert missing.status_code == 404
