"""Search helpers for knowledge-base routes."""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, Workspace
from app.schemas.knowledge_base import (
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
)
from app.services.knowledge_base_documents import resolve_request_scope
from app.services.knowledge_base_presenters import search_result_from_document
from app.services.rag_runtime import get_rag_service

ScopeResolver = Callable[..., Awaitable[list[str] | None]]
RAGServiceFactory = Callable[[], object]
SearchResultPresenter = Callable[[object], object]


async def search_knowledge_base_documents(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase,
    workspace: Workspace,
    resolve_scope: ScopeResolver = resolve_request_scope,
    rag_service_factory: RAGServiceFactory = get_rag_service,
    result_presenter: SearchResultPresenter = search_result_from_document,
) -> KnowledgeBaseSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    bvids = await resolve_scope(
        db,
        knowledge_base_id=knowledge_base.id,
        folder_ids=payload.folder_ids,
        bvids=payload.bvids,
    )
    k = max(1, min(payload.k, 20))
    rag = rag_service_factory()
    documents = rag.search_in_knowledge_base(
        query,
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
        bvids=bvids,
    )
    return KnowledgeBaseSearchResponse(
        results=[result_presenter(document) for document in documents]
    )
