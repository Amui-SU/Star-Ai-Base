from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.knowledge_base_build_route_runtime import (
    start_knowledge_base_build,
)


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, **kwargs):
        self.tasks.append((func, kwargs))


@pytest.mark.asyncio
async def test_start_knowledge_base_build_prepares_dependencies_and_schedules_runner():
    background_tasks = FakeBackgroundTasks()
    calls = []

    async def prepare_build_request(_db, **kwargs):
        calls.append(("prepare", kwargs))
        assert kwargs["rag_service_factory"]() == "resolved-rag"
        return SimpleNamespace(response="build-response", task_kwargs={"task_id": "t1"})

    def resolve_rag_service(*, rag_service_factory, warning_logger):
        calls.append(("resolve", rag_service_factory(), warning_logger))
        return "resolved-rag"

    async def runner(**_kwargs):
        raise AssertionError("background runner should only be scheduled")

    result = await start_knowledge_base_build(
        db=object(),
        payload=object(),
        background_tasks=background_tasks,
        user=SimpleNamespace(id=1),
        workspace=SimpleNamespace(id=2),
        knowledge_base=SimpleNamespace(id=3),
        bilibili_service_class=object,
        asr_service_factory=lambda: "asr",
        content_fetcher_class=object,
        rag_service_factory=lambda: "raw-rag",
        run_scoped_build=runner,
        warning_logger=lambda message: calls.append(("warning", message)),
        prepare_build_request=prepare_build_request,
        resolve_rag_service=resolve_rag_service,
    )

    assert result == "build-response"
    assert background_tasks.tasks == [(runner, {"task_id": "t1"})]
    prepare_kwargs = calls[0][1]
    assert prepare_kwargs["user"].id == 1
    assert prepare_kwargs["workspace"].id == 2
    assert prepare_kwargs["knowledge_base"].id == 3
    assert prepare_kwargs["bilibili_service_class"] is object
    assert prepare_kwargs["asr_service_factory"]() == "asr"
    assert prepare_kwargs["content_fetcher_class"] is object
    assert calls[1][0] == "resolve"
    assert calls[1][1] == "raw-rag"


@pytest.mark.asyncio
async def test_start_knowledge_base_build_does_not_schedule_when_prepare_fails():
    background_tasks = FakeBackgroundTasks()

    async def prepare_build_request(_db, **_kwargs):
        raise HTTPException(status_code=404, detail="Source binding not found")

    async def runner(**_kwargs):
        raise AssertionError("background runner should not be scheduled")

    with pytest.raises(HTTPException) as exc_info:
        await start_knowledge_base_build(
            db=object(),
            payload=object(),
            background_tasks=background_tasks,
            user=object(),
            workspace=object(),
            knowledge_base=object(),
            bilibili_service_class=object,
            asr_service_factory=object,
            content_fetcher_class=object,
            rag_service_factory=object,
            run_scoped_build=runner,
            warning_logger=lambda _message: None,
            prepare_build_request=prepare_build_request,
        )

    assert exc_info.value.status_code == 404
    assert background_tasks.tasks == []
