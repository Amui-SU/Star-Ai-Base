"""Presentation and small utility helpers for knowledge-base routes."""

import inspect

from sqlalchemy import and_, or_

from app.schemas.knowledge_base import (
    KnowledgeBaseResponse,
    KnowledgeBaseSearchResult,
)
from app.services.bilibili_multi_part import bilibili_video_url


def supports_keyword_argument(callable_obj, keyword: str) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return True
    return keyword in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def response_from_knowledge_base(knowledge_base) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        name=knowledge_base.name,
        description=knowledge_base.description,
    )


def search_result_from_document(document) -> KnowledgeBaseSearchResult:
    metadata = document.metadata or {}
    return KnowledgeBaseSearchResult(
        content=document.page_content,
        bvid=metadata.get("bvid"),
        title=metadata.get("title"),
        url=metadata.get("url"),
    )


def source_from_document(document) -> dict:
    metadata = document.metadata or {}
    bvid = metadata.get("bvid")
    return {
        "type": "knowledge",
        "bvid": bvid,
        "title": metadata.get("title") or bvid or "Untitled",
        "url": metadata.get("url") or bilibili_video_url(bvid or ""),
    }


def dedupe_ints(values: list[int] | None) -> list[int]:
    return list(dict.fromkeys(values or []))


def dedupe_strings(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(item for item in (values or []) if item))


def nullable_equal(left, right):
    return or_(left == right, and_(left.is_(None), right.is_(None)))
