from types import SimpleNamespace

import pytest

from app.services.knowledge_base_route_runtime import (
    delete_knowledge_base_from_router,
    get_knowledge_base_build_status_from_router,
    search_knowledge_base_from_router,
)


@pytest.mark.asyncio
async def test_build_status_runtime_delegates_to_status_service():
    db = object()
    knowledge_base = SimpleNamespace(id=11)
    calls = []

    async def get_status_payload(db_arg, *, task_id, knowledge_base):
        calls.append((db_arg, task_id, knowledge_base))
        return {"status": "completed"}

    result = await get_knowledge_base_build_status_from_router(
        db,
        task_id="task-1",
        knowledge_base=knowledge_base,
        get_status_payload=get_status_payload,
    )

    assert result == {"status": "completed"}
    assert calls == [(db, "task-1", knowledge_base)]


@pytest.mark.asyncio
async def test_search_runtime_delegates_with_router_rag_factory():
    db = object()
    payload = SimpleNamespace(query="search")
    knowledge_base = SimpleNamespace(id=12)
    workspace = SimpleNamespace(id=7)
    rag_factory = object()
    calls = []

    async def search_documents(
        db_arg,
        *,
        payload,
        knowledge_base,
        workspace,
        rag_service_factory,
    ):
        calls.append((db_arg, payload, knowledge_base, workspace, rag_service_factory))
        return "search-response"

    result = await search_knowledge_base_from_router(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        workspace=workspace,
        rag_service_factory=rag_factory,
        search_documents=search_documents,
    )

    assert result == "search-response"
    assert calls == [(db, payload, knowledge_base, workspace, rag_factory)]


@pytest.mark.asyncio
async def test_delete_runtime_delegates_with_router_compat_dependencies():
    db = object()
    knowledge_base = SimpleNamespace(id=12)
    workspace = SimpleNamespace(id=7)
    rag_factory = object()
    keyword_checker = object()
    info_logger = object()
    warning_logger = object()
    calls = []

    async def delete_knowledge_base(
        db_arg,
        *,
        knowledge_base,
        workspace,
        rag_service_factory,
        supports_keyword_argument_func,
        info_logger,
        warning_logger,
    ):
        calls.append(
            (
                db_arg,
                knowledge_base,
                workspace,
                rag_service_factory,
                supports_keyword_argument_func,
                info_logger,
                warning_logger,
            )
        )
        return {"ok": True, "deleted_vectors": 2}

    result = await delete_knowledge_base_from_router(
        db,
        knowledge_base=knowledge_base,
        workspace=workspace,
        rag_service_factory=rag_factory,
        supports_keyword_argument_func=keyword_checker,
        info_logger=info_logger,
        warning_logger=warning_logger,
        delete_knowledge_base=delete_knowledge_base,
    )

    assert result == {"ok": True, "deleted_vectors": 2}
    assert calls == [
        (
            db,
            knowledge_base,
            workspace,
            rag_factory,
            keyword_checker,
            info_logger,
            warning_logger,
        )
    ]
