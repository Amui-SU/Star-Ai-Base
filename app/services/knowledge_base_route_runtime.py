"""Router dependency assembly for knowledge-base maintenance endpoints."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, Workspace
from app.schemas.knowledge_base import (
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
)
from app.services.knowledge_base_build_tasks import get_build_status_payload
from app.services.knowledge_base_delete import (
    delete_knowledge_base as delete_knowledge_base_service,
)
from app.services.knowledge_base_search import search_knowledge_base_documents

StatusPayloadGetter = Callable[..., Awaitable[dict]]
RAGServiceFactory = Callable[[], object]
KeywordSupportChecker = Callable[[Callable, str], bool]
MessageLogger = Callable[[str], None]
SearchDocuments = Callable[..., Awaitable[KnowledgeBaseSearchResponse]]
DeleteKnowledgeBase = Callable[..., Awaitable[dict]]


async def get_knowledge_base_build_status_from_router(
    db: AsyncSession,
    *,
    task_id: str,
    knowledge_base: KnowledgeBase,
    get_status_payload: StatusPayloadGetter = get_build_status_payload,
) -> dict:
    return await get_status_payload(
        db,
        task_id=task_id,
        knowledge_base=knowledge_base,
    )


async def search_knowledge_base_from_router(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase,
    workspace: Workspace,
    rag_service_factory: RAGServiceFactory,
    search_documents: SearchDocuments = search_knowledge_base_documents,
) -> KnowledgeBaseSearchResponse:
    return await search_documents(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        workspace=workspace,
        rag_service_factory=rag_service_factory,
    )


async def delete_knowledge_base_from_router(
    db: AsyncSession,
    *,
    knowledge_base: KnowledgeBase,
    workspace: Workspace,
    rag_service_factory: RAGServiceFactory,
    supports_keyword_argument_func: KeywordSupportChecker,
    info_logger: MessageLogger,
    warning_logger: MessageLogger,
    delete_knowledge_base: DeleteKnowledgeBase = delete_knowledge_base_service,
) -> dict:
    return await delete_knowledge_base(
        db,
        knowledge_base=knowledge_base,
        workspace=workspace,
        rag_service_factory=rag_service_factory,
        supports_keyword_argument_func=supports_keyword_argument_func,
        info_logger=info_logger,
        warning_logger=warning_logger,
    )
