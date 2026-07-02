"""Router-level runtime assembly for knowledge-base build requests."""

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.knowledge_base import KnowledgeBaseBuildRequest
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.knowledge_base_build_requests import (
    prepare_knowledge_base_build_request,
)
from app.services.knowledge_base_build_runtime import resolve_build_rag_service
from app.services.knowledge_base_build_tasks import run_scoped_build
from app.services.rag_runtime import get_rag_service


async def start_knowledge_base_build(
    *,
    db: AsyncSession,
    payload: KnowledgeBaseBuildRequest,
    background_tasks: Any,
    user: Any,
    workspace: Any,
    knowledge_base: Any,
    bilibili_service_class: type = BilibiliService,
    asr_service_factory: Callable[[], Any] = ASRService,
    content_fetcher_class: type = ContentFetcher,
    rag_service_factory: Callable[[], Any] = get_rag_service,
    run_scoped_build: Callable[..., Any] = run_scoped_build,
    warning_logger: Callable[[str], None] = lambda _message: None,
    prepare_build_request: Callable[..., Any] = prepare_knowledge_base_build_request,
    resolve_rag_service: Callable[..., Any] = resolve_build_rag_service,
):
    def build_rag_service():
        return resolve_rag_service(
            rag_service_factory=rag_service_factory,
            warning_logger=warning_logger,
        )

    plan = await prepare_build_request(
        db,
        payload=payload,
        user=user,
        workspace=workspace,
        knowledge_base=knowledge_base,
        bilibili_service_class=bilibili_service_class,
        asr_service_factory=asr_service_factory,
        content_fetcher_class=content_fetcher_class,
        rag_service_factory=build_rag_service,
    )

    background_tasks.add_task(
        run_scoped_build,
        **plan.task_kwargs,
    )

    return plan.response
