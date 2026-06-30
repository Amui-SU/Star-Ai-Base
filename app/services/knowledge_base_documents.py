"""Document loading helpers for knowledge-base scoped chat/search."""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from langchain.schema import Document
from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FavoriteVideo,
    KnowledgeBase,
    KnowledgeBaseChatRequest,
    VideoCache,
    Workspace,
)
from app.services.knowledge_base_presenters import nullable_equal
from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids
from app.services.rag_runtime import get_rag_service

ScopeResolver = Callable[..., Awaitable[list[str] | None]]
FallbackDocumentLoader = Callable[..., Awaitable[list]]


def video_cache_matches_favorite():
    return and_(
        FavoriteVideo.bvid == VideoCache.bvid,
        nullable_equal(FavoriteVideo.workspace_id, VideoCache.workspace_id),
        nullable_equal(
            FavoriteVideo.knowledge_base_id,
            VideoCache.knowledge_base_id,
        ),
        nullable_equal(FavoriteVideo.source_binding_id, VideoCache.source_binding_id),
    )


async def resolve_request_scope(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
    folder_ids: list[int] | None,
    bvids: list[str] | None,
) -> list[str] | None:
    try:
        return await resolve_scope_bvids(
            db,
            knowledge_base_id=knowledge_base_id,
            folder_media_ids=folder_ids,
            requested_bvids=bvids,
        )
    except InvalidKnowledgeScope as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def load_db_fallback_documents(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
    bvids: list[str] | None,
    k: int,
) -> list:
    stmt = (
        select(
            VideoCache.bvid,
            VideoCache.title,
            VideoCache.description,
            VideoCache.content,
        )
        .join(FavoriteVideo, video_cache_matches_favorite())
        .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
        .where(VideoCache.is_processed.is_(True))
    )
    if bvids is not None:
        if not bvids:
            return []
        stmt = stmt.where(FavoriteVideo.bvid.in_(bvids))
    stmt = stmt.limit(max(1, k))

    rows = await db.execute(stmt)
    documents = []
    seen_bvids = set()
    for bvid, title, description, content in rows.fetchall():
        if not bvid or bvid in seen_bvids:
            continue
        text = (content or description or title or "").strip()
        if not text:
            continue
        seen_bvids.add(bvid)
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "bvid": bvid,
                    "title": title or bvid,
                    "url": f"https://www.bilibili.com/video/{bvid}",
                },
            )
        )
    return documents


async def load_scoped_chat_documents(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    allow_db_fallback: bool = True,
    resolve_request_scope_func: ScopeResolver | None = None,
    load_db_fallback_documents_func: FallbackDocumentLoader | None = None,
    rag_service_factory: Callable[[], object] = get_rag_service,
    warning_logger: Callable[[str], None] = logger.warning,
) -> list:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    scope_resolver = resolve_request_scope_func or resolve_request_scope
    fallback_loader = load_db_fallback_documents_func or load_db_fallback_documents
    bvids = await scope_resolver(
        db,
        knowledge_base_id=knowledge_base.id,
        folder_ids=payload.folder_ids,
        bvids=payload.bvids,
    )
    k = max(1, min(payload.k, 20))
    try:
        documents = rag_service_factory().search_in_knowledge_base(
            question,
            workspace_id=current_workspace.id,
            knowledge_base_id=knowledge_base.id,
            k=k,
            bvids=bvids,
        )
        if documents:
            return documents
        return []
    except Exception as exc:
        warning_logger(
            f"知识库向量检索不可用 [{knowledge_base.id}]，回退到数据库内容: {exc}"
        )

    if not allow_db_fallback:
        return []

    return await fallback_loader(
        db,
        knowledge_base_id=knowledge_base.id,
        bvids=bvids,
        k=k,
    )
