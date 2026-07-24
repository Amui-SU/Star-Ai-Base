"""Non-streaming knowledge-base chat orchestration."""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgeBase,
    SystemUser,
    Workspace,
)
from app.schemas.chat import ChatResponse
from app.schemas.knowledge_base import KnowledgeBaseChatRequest
from app.services.llm_errors import classify_upstream_error


async def answer_knowledge_base_chat(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    user: SystemUser,
    workspace: Workspace,
    load_documents: Callable[..., Awaitable[list[Any]]],
    answer_from_documents: Callable[[str, list[Any]], ChatResponse],
    resolve_llm_credentials: Callable[..., Awaitable[Any]],
    global_config_resolver: Callable[..., Any],
    resolve_web_search_api_key: Callable[..., Awaitable[str | None]],
    build_messages: Callable[..., list[dict]],
    complete_answer: Callable[
        ...,
        Awaitable[tuple[str, str, list[dict[str, str]], dict | None]],
    ],
    supports_keyword_argument: Callable[[Callable[..., Any], str], bool],
    record_usage: Callable[..., Awaitable[Any]],
    source_from_document: Callable[[Any], dict[str, str]],
    source_from_web_result: Callable[[dict[str, str]], dict[str, str]],
    web_search_failed_status_from_exception: Callable[[Exception], dict],
    warning_logger: Callable[[str], None],
) -> ChatResponse:
    question = payload.question.strip()
    documents = await load_documents(
        payload,
        knowledge_base,
        workspace,
        db,
        allow_db_fallback=not payload.web_search,
    )
    if not documents and not payload.web_search:
        return answer_from_documents(question, documents)

    credential = await resolve_llm_credentials(
        db,
        user,
        global_config_resolver=global_config_resolver,
    )
    llm_config = credential.to_llm_config()
    tavily_api_key = await resolve_web_search_api_key(
        db,
        user,
        enabled=payload.web_search,
        provider=payload.web_search_provider,
    )

    messages = build_messages(
        question,
        documents,
        enable_web_search=payload.web_search,
        thinking_config=llm_config["thinking_config"],
    )
    try:
        complete_kwargs = {
            "question": question,
            "enable_web_search": payload.web_search,
        }
        if supports_keyword_argument(complete_answer, "web_search_provider"):
            complete_kwargs["web_search_provider"] = payload.web_search_provider
        if supports_keyword_argument(complete_answer, "tavily_api_key"):
            complete_kwargs["tavily_api_key"] = tavily_api_key
        if supports_keyword_argument(complete_answer, "llm_config"):
            complete_kwargs["llm_config"] = llm_config
        answer, thinking, web_results, web_search_status = await complete_answer(
            messages,
            **complete_kwargs,
        )
    except Exception as exc:
        await record_usage(
            db,
            user=user,
            credential=credential,
            feature="chat",
            status="failed",
            error_code=exc.__class__.__name__,
        )
        await db.commit()
        failure = classify_upstream_error(exc)
        warning_logger(failure.log_message("知识库模型回答失败，回退到检索内容"))
        response = answer_from_documents(question, documents)
        if payload.web_search:
            response.web_search = web_search_failed_status_from_exception(exc)
        return response

    await record_usage(
        db,
        user=user,
        credential=credential,
        feature="chat",
        status="success",
    )
    await db.commit()
    return ChatResponse(
        answer=answer,
        thinking=thinking or None,
        sources=[
            *[source_from_document(document) for document in documents],
            *[source_from_web_result(result) for result in web_results],
        ],
        web_search=web_search_status,
    )
