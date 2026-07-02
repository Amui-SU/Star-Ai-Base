"""RAG vector search helpers."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain.schema import Document
from loguru import logger

from app.services.rag_filters import knowledge_base_filter


def legacy_similarity_search(
    query: str,
    *,
    vectorstore: Any,
    k: int = 5,
    bvids: Sequence[str] | None = None,
    warning_logger: Callable[[str], None] = logger.warning,
    info_logger: Callable[[str], None] = logger.info,
) -> list[Document]:
    """Run legacy unscoped similarity search with existing logging semantics."""
    if not query or not query.strip():
        warning_logger("检索查询为空")
        return []

    try:
        if bvids:
            docs = vectorstore.similarity_search(
                query, k=k, filter={"bvid": {"$in": list(bvids)}}
            )
        else:
            docs = vectorstore.similarity_search(query, k=k)

        info_logger(f"检索完成：query='{query}'，召回={len(docs)}")
        for index, doc in enumerate(docs, start=1):
            meta = doc.metadata or {}
            title = meta.get("title", "")
            bvid = meta.get("bvid", "")
            chunk_index = meta.get("chunk_index", "")
            preview = doc.page_content[:120].replace("\n", " ").strip()
            info_logger(f"召回[{index}] {bvid} #{chunk_index} {title} | {preview}")

        return docs
    except Exception as exc:
        warning_logger(f"向量检索失败: {exc}")
        return []


def scoped_similarity_search(
    query: str,
    *,
    vectorstore: Any,
    workspace_id: int,
    knowledge_base_id: int,
    k: int = 5,
    bvids: Sequence[str] | None = None,
) -> list[Document]:
    """Run scoped similarity search for one workspace and knowledge base."""
    if not query or not query.strip():
        return []

    return vectorstore.similarity_search(
        query,
        k=k,
        filter=knowledge_base_filter(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvids=bvids,
        ),
    )
