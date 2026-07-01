"""Deletion helpers for knowledge-base routes."""

from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    KnowledgeBase,
    VideoCache,
    VideoTitleOverride,
    Workspace,
)
from app.services.knowledge_base_presenters import supports_keyword_argument
from app.services.rag_runtime import get_rag_service


RAGServiceFactory = Callable[[], object]
KeywordSupportChecker = Callable[[Callable, str], bool]
MessageLogger = Callable[[str], None]


def delete_knowledge_base_vectors(
    knowledge_base: KnowledgeBase,
    *,
    workspace: Workspace,
    rag_service_factory: RAGServiceFactory = get_rag_service,
    supports_keyword_argument_func: KeywordSupportChecker = supports_keyword_argument,
) -> int:
    rag = rag_service_factory()
    if supports_keyword_argument_func(
        rag.delete_by_knowledge_base,
        "workspace_id",
    ):
        return rag.delete_by_knowledge_base(
            knowledge_base.id,
            workspace_id=workspace.id,
        )
    return rag.delete_by_knowledge_base(knowledge_base.id)


async def delete_knowledge_base_records(
    db: AsyncSession,
    *,
    knowledge_base: KnowledgeBase,
) -> None:
    knowledge_base_id = knowledge_base.id

    await db.execute(
        IngestionTask.__table__.delete().where(
            IngestionTask.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        FavoriteFolder.__table__.delete().where(
            FavoriteFolder.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        FavoriteVideo.__table__.delete().where(
            FavoriteVideo.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        VideoCache.__table__.delete().where(
            VideoCache.knowledge_base_id == knowledge_base_id
        )
    )
    await db.execute(
        VideoTitleOverride.__table__.delete().where(
            VideoTitleOverride.knowledge_base_id == knowledge_base_id
        )
    )
    await db.delete(knowledge_base)


async def delete_knowledge_base(
    db: AsyncSession,
    *,
    knowledge_base: KnowledgeBase,
    workspace: Workspace,
    rag_service_factory: RAGServiceFactory = get_rag_service,
    supports_keyword_argument_func: KeywordSupportChecker = supports_keyword_argument,
    info_logger: MessageLogger | None = None,
    warning_logger: MessageLogger | None = None,
) -> dict[str, object]:
    knowledge_base_id = knowledge_base.id

    try:
        deleted_vectors = delete_knowledge_base_vectors(
            knowledge_base,
            workspace=workspace,
            rag_service_factory=rag_service_factory,
            supports_keyword_argument_func=supports_keyword_argument_func,
        )
        if info_logger:
            info_logger(
                f"已删除知识库 {knowledge_base_id}（{knowledge_base.name}）的 {deleted_vectors} 个向量"
            )
    except Exception as exc:
        if warning_logger:
            warning_logger(f"删除知识库向量失败[{knowledge_base_id}]: {exc}")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "vector_cleanup_failed",
                "message": f"向量清理失败，知识库未删除，请稍后重试或检查向量服务：{exc}",
            },
        ) from exc

    await delete_knowledge_base_records(db, knowledge_base=knowledge_base)
    await db.commit()
    return {"ok": True, "deleted_vectors": deleted_vectors}
