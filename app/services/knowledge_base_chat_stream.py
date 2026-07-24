"""Streaming knowledge-base chat orchestration."""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, SystemUser, Workspace
from app.schemas.knowledge_base import KnowledgeBaseChatRequest
from app.services.llm_errors import classify_upstream_error


async def stream_knowledge_base_chat(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    user: SystemUser,
    workspace: Workspace,
    load_documents: Callable[..., Awaitable[list[Any]]],
    answer_from_documents: Callable[[str, list[Any]], Any],
    resolve_llm_credentials: Callable[..., Awaitable[Any]],
    global_config_resolver: Callable[..., Any],
    resolve_web_search_api_key: Callable[..., Awaitable[str | None]],
    build_messages: Callable[..., list[dict]],
    prepare_web_search_with_heartbeats: Callable[..., AsyncIterator[tuple[str, Any]]],
    append_no_more_tool_calls_instruction: Callable[[list[dict]], list[dict]],
    stream_llm_events: Callable[..., Iterable[tuple[str, str]]],
    supports_keyword_argument: Callable[[Callable[..., Any], str], bool],
    encode_web_search_progress: Callable[[str], str],
    encode_thinking_delta: Callable[[str], str],
    source_from_document: Callable[[Any], dict[str, str]],
    source_from_web_result: Callable[[dict[str, str]], dict[str, str]],
    web_search_failed_status_from_exception: Callable[[Exception], dict],
    record_usage: Callable[..., Awaitable[Any]],
    warning_logger: Callable[[str], None],
) -> AsyncIterator[str]:
    question = payload.question.strip()
    documents = await load_documents(
        payload,
        knowledge_base,
        workspace,
        db,
        allow_db_fallback=not payload.web_search,
    )
    credential = None
    llm_config = None
    if documents or payload.web_search:
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

    async def generate() -> AsyncIterator[str]:
        if not documents and not payload.web_search:
            yield answer_from_documents(question, documents).answer
            yield "\n[[SOURCES_JSON]][]"
            return

        messages = build_messages(
            question,
            documents,
            enable_web_search=payload.web_search,
            thinking_config=llm_config["thinking_config"] if llm_config else None,
        )
        web_results: list[dict[str, str]] = []
        web_search_status = None
        prepared_messages = messages
        thinking_parts: list[str] = []
        if payload.web_search:
            yield encode_web_search_progress("正在联网搜索外部资料")
            try:
                async for (
                    event_type,
                    event_payload,
                ) in prepare_web_search_with_heartbeats(
                    messages,
                    question=question,
                    provider=payload.web_search_provider,
                    tavily_api_key=tavily_api_key,
                    llm_config=llm_config,
                ):
                    if event_type == "heartbeat":
                        yield encode_web_search_progress(str(event_payload))
                        continue
                    tool_run, web_results, web_search_status = event_payload
                prepared_messages = append_no_more_tool_calls_instruction(
                    tool_run.messages
                )
            except Exception as exc:
                failure = classify_upstream_error(exc)
                warning_logger(
                    failure.log_message("知识库联网工具链准备失败，将仅使用知识库回答")
                )
                web_search_status = web_search_failed_status_from_exception(exc)
            finally:
                yield encode_web_search_progress("")

        sources = [
            *[source_from_document(document) for document in documents],
            *[source_from_web_result(result) for result in web_results],
        ]
        answer_started = False
        try:
            stream_kwargs = {}
            if supports_keyword_argument(stream_llm_events, "llm_config"):
                stream_kwargs["llm_config"] = llm_config
            for event_type, content in stream_llm_events(
                prepared_messages,
                **stream_kwargs,
            ):
                if event_type == "thinking":
                    thinking_parts.append(content)
                    yield encode_thinking_delta(content)
                else:
                    answer_started = True
                    yield content
        except Exception as exc:
            failure = classify_upstream_error(exc)
            warning_logger(
                failure.log_message("知识库流式模型回答失败，回退到检索内容")
            )
            if not answer_started:
                yield answer_from_documents(question, documents).answer

        if thinking_parts:
            yield "\n[[THINKING_JSON]]"
            yield json.dumps("".join(thinking_parts), ensure_ascii=False)
        if web_search_status:
            yield "\n[[WEB_SEARCH_JSON]]"
            yield json.dumps(web_search_status, ensure_ascii=False)
        yield "\n[[SOURCES_JSON]]"
        yield json.dumps(sources, ensure_ascii=False)
        if credential is not None:
            await record_usage(
                db,
                user=user,
                credential=credential,
                feature="chat",
                status="success",
            )
            await db.commit()

    return generate()
