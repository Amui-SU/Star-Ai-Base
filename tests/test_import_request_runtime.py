from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.import_request_runtime import (
    detect_import_source_type,
    extract_bilibili_bvid,
    prepare_bilibili_import_request,
    prepare_local_video_import_request,
)


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, **kwargs):
        self.tasks.append((func, kwargs))


class FakeUploadFile:
    def __init__(self, filename, content_type, data=b"video bytes"):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(data)
        self.closed = False

    async def close(self):
        self.closed = True


class FakeDb:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base

    async def get(self, _model, knowledge_base_id):
        if self.knowledge_base and self.knowledge_base.id == knowledge_base_id:
            return self.knowledge_base
        return None


def test_import_request_runtime_detects_supported_source_types():
    assert detect_import_source_type("https://www.bilibili.com/video/BV1234567890")
    assert (
        detect_import_source_type("https://example.com/watch/BV1234567890")
        == "bilibili_video"
    )
    assert detect_import_source_type("https://www.douyin.com/video/123") == "douyin"
    assert detect_import_source_type("https://example.com/page") == "url"
    assert detect_import_source_type("https://example.com/page", "manual") == "manual"
    assert extract_bilibili_bvid("https://example.com/BV1234567890") == "BV1234567890"


@pytest.mark.asyncio
async def test_prepare_bilibili_import_request_creates_task_and_schedules_runner():
    background_tasks = FakeBackgroundTasks()
    created_tasks = []

    async def create_task(_db, **kwargs):
        created_tasks.append(kwargs)
        return "task-1"

    async def runner(**_kwargs):
        raise AssertionError("background runner should only be scheduled")

    result = await prepare_bilibili_import_request(
        url="https://www.bilibili.com/video/BV1234567890",
        requested_source_type="auto",
        knowledge_base_id=9,
        background_tasks=background_tasks,
        current_user=SimpleNamespace(id=5),
        current_workspace=SimpleNamespace(id=3),
        db=FakeDb(SimpleNamespace(id=9, workspace_id=3)),
        run_bilibili_video_import=runner,
        create_task=create_task,
    )

    assert result == {
        "ok": True,
        "status": "pending",
        "source_type": "bilibili_video",
        "message": "已创建视频导入任务",
        "task_id": "task-1",
        "bvid": "BV1234567890",
    }
    assert created_tasks == [
        {
            "workspace_id": 3,
            "knowledge_base_id": 9,
            "user_id": 5,
            "current_step": "准备导入 BV1234567890",
            "total_items": 1,
        }
    ]
    assert background_tasks.tasks == [
        (
            runner,
            {
                "task_id": "task-1",
                "bvid": "BV1234567890",
                "workspace_id": 3,
                "knowledge_base_id": 9,
            },
        )
    ]


@pytest.mark.asyncio
async def test_prepare_bilibili_import_request_reports_unsupported_and_bad_bvid():
    unsupported = await prepare_bilibili_import_request(
        url="https://example.com/page",
        requested_source_type="auto",
        knowledge_base_id=9,
        background_tasks=FakeBackgroundTasks(),
        current_user=SimpleNamespace(id=5),
        current_workspace=SimpleNamespace(id=3),
        db=FakeDb(SimpleNamespace(id=9, workspace_id=3)),
        run_bilibili_video_import=lambda **_kwargs: None,
        create_task=lambda *_args, **_kwargs: "unused",
    )

    assert unsupported["ok"] is False
    assert unsupported["status"] == "unsupported"
    assert unsupported["source_type"] == "url"

    with pytest.raises(HTTPException) as exc_info:
        await prepare_bilibili_import_request(
            url="https://www.bilibili.com/video/not-a-bvid",
            requested_source_type="bilibili_video",
            knowledge_base_id=9,
            background_tasks=FakeBackgroundTasks(),
            current_user=SimpleNamespace(id=5),
            current_workspace=SimpleNamespace(id=3),
            db=FakeDb(SimpleNamespace(id=9, workspace_id=3)),
            run_bilibili_video_import=lambda **_kwargs: None,
            create_task=lambda *_args, **_kwargs: "unused",
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_prepare_local_video_import_request_stores_upload_and_schedules_runner(
    tmp_path,
):
    background_tasks = FakeBackgroundTasks()
    created_tasks = []

    async def create_task(_db, **kwargs):
        created_tasks.append(kwargs)
        return "local-task"

    async def runner(**_kwargs):
        raise AssertionError("background runner should only be scheduled")

    upload = FakeUploadFile("demo.mkv", "video/x-matroska")

    result = await prepare_local_video_import_request(
        knowledge_base_id=9,
        title=" Demo Title ",
        file=upload,
        background_tasks=background_tasks,
        current_user=SimpleNamespace(id=5),
        current_workspace=SimpleNamespace(id=3),
        db=FakeDb(SimpleNamespace(id=9, workspace_id=3)),
        run_local_video_import=runner,
        create_task=create_task,
        local_import_dir=tmp_path,
        local_video_id_factory=lambda: "LVTESTVIDEO",
    )

    stored_path = tmp_path / "LVTESTVIDEO.mkv"
    assert stored_path.read_bytes() == b"video bytes"
    assert upload.closed is True
    assert result == {
        "ok": True,
        "status": "pending",
        "source_type": "local_video",
        "message": "已创建本地视频导入任务",
        "task_id": "local-task",
        "bvid": "LVTESTVIDEO",
    }
    assert created_tasks[0]["current_step"] == "准备导入 Demo Title"
    assert background_tasks.tasks == [
        (
            runner,
            {
                "task_id": "local-task",
                "local_id": "LVTESTVIDEO",
                "title": "Demo Title",
                "file_path": str(stored_path),
                "workspace_id": 3,
                "knowledge_base_id": 9,
            },
        )
    ]


@pytest.mark.asyncio
async def test_prepare_local_video_import_request_rejects_non_video_file(tmp_path):
    with pytest.raises(HTTPException) as exc_info:
        await prepare_local_video_import_request(
            knowledge_base_id=9,
            title=None,
            file=FakeUploadFile("notes.txt", "text/plain"),
            background_tasks=FakeBackgroundTasks(),
            current_user=SimpleNamespace(id=5),
            current_workspace=SimpleNamespace(id=3),
            db=FakeDb(SimpleNamespace(id=9, workspace_id=3)),
            run_local_video_import=lambda **_kwargs: None,
            create_task=lambda *_args, **_kwargs: "unused",
            local_import_dir=tmp_path,
        )

    assert exc_info.value.status_code == 400
