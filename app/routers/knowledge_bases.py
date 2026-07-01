import sys
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
    get_knowledge_base_for_user_readonly,
)
from app.models import (
    KnowledgeBase,
    SystemUser,
    Workspace,
)
from app.schemas.chat import ChatResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeScopeOptionsResponse,
)
from app.services.rag_runtime import get_rag_service
from app.services.knowledge_base_catalog import (
    create_workspace_knowledge_base,
    list_workspace_knowledge_bases,
)
from app.services.knowledge_base_build_requests import (
    prepare_knowledge_base_build_request,
)
from app.services.knowledge_base_build_runtime import resolve_build_rag_service
from app.services.knowledge_base_build_tasks import (
    get_build_status_payload,
    run_scoped_build as _run_scoped_build,
)
from app.services.knowledge_base_answer_adapter import (
    build_complete_knowledge_base_answer,
)
from app.services.knowledge_base_chat import answer_knowledge_base_chat
from app.services.knowledge_base_chat_stream import stream_knowledge_base_chat
from app.services.knowledge_base_delete import (
    delete_knowledge_base as delete_knowledge_base_service,
)
from app.services.knowledge_base_documents import (
    load_db_fallback_documents as _load_db_fallback_documents,
    load_scoped_chat_documents as _load_scoped_chat_documents_impl,
    resolve_request_scope as _resolve_request_scope,
)
from app.services.knowledge_base_presenters import (
    source_from_document as _source_from_document,
    supports_keyword_argument as _supports_keyword_argument,
)
from app.services.knowledge_base_messages import (
    answer_from_documents,
    build_knowledge_base_messages,
)
from app.services.knowledge_base_stats import build_knowledge_base_stats
from app.services.knowledge_base_search import search_knowledge_base_documents
from app.services.chat_messages import (
    apply_mode_instructions as _apply_mode_instructions,
    enforce_markdown_output as _enforce_markdown_output,
)
from app.services.chat_completion import (
    complete_llm_answer,
    encode_thinking_delta,
    prepare_llm_messages_with_tools,
    stream_llm_events,
)
from app.services.chat_provider_catalog import _resolve_llm_config
from app.services.knowledge_base_llm_runtime import (
    build_complete_llm_answer_adapter,
    build_prepare_llm_messages_with_tools_adapter,
    build_stream_llm_events_adapter,
    encode_web_search_progress as _encode_web_search_progress,
)
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.llm_tool_calls import (
    append_no_more_tool_calls_instruction as _append_no_more_tool_calls_instruction,
)
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.knowledge_scope import (
    list_scope_options,
)
from app.services.knowledge_web_search import (
    FETCH_WEB_PAGE_TOOL,
    MAX_INITIAL_WEB_SEARCH_QUERIES,
    MAX_WEB_CONTEXT_RESULTS,
    MAX_WEB_SEARCH_QUERY_CHARS,
    WEB_SEARCH_TOOL,
    append_unique_query as _append_unique_query,
    append_web_result as _append_web_result,
    append_web_search_context_message as _append_web_search_context_message,
    append_web_search_diagnostics as _append_web_search_diagnostics,
    append_web_search_no_results_message as _append_web_search_no_results_message,
    build_web_search_queries as _build_web_search_queries,
    compact_web_search_query as _compact_web_search_query,
    format_web_search_context as _format_web_search_context,
    normalize_web_search_query as _normalize_web_search_query,
    remove_web_search_no_results_messages as _remove_web_search_no_results_messages,
    source_from_web_result as _source_from_web_result,
    status_from_web_search_state as _status_from_web_search_state,
    web_search_failed_status_from_exception as _web_search_failed_status_from_exception,
    web_search_status as _web_search_status,
)
from app.services.knowledge_base_web_search_compat import (
    build_web_search_orchestration_compat,
)
from app.services.knowledge_base_web_search_api_key import (
    resolve_web_search_api_key as resolve_knowledge_base_web_search_api_key,
)
from app.services.api_credentials import (
    record_usage_event,
    resolve_optional_user_api_credentials,
    resolve_user_llm_credentials,
)
from app.services.web_search import fetch_web_page, search_web

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def _encode_thinking_delta(content: str) -> str:
    return encode_thinking_delta(content)


_stream_llm_events = build_stream_llm_events_adapter(
    stream_llm_events=stream_llm_events,
    resolve_llm_config=lambda: _resolve_llm_config(),
    get_llm_client=lambda config: _get_llm_client(config),
)

_complete_llm_answer = build_complete_llm_answer_adapter(
    complete_llm_answer=complete_llm_answer,
    resolve_llm_config=lambda: _resolve_llm_config(),
    get_llm_client=lambda config: _get_llm_client(config),
)

_prepare_llm_messages_with_tools = build_prepare_llm_messages_with_tools_adapter(
    prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
    resolve_llm_config=lambda: _resolve_llm_config(),
    get_llm_client=lambda config: _get_llm_client(config),
)


def _get_rag_service_for_build():
    return resolve_build_rag_service(
        rag_service_factory=lambda: get_rag_service(),
        warning_logger=logger.warning,
    )


_answer_from_documents = lambda question, documents: answer_from_documents(
    question,
    documents,
    source_from_document=_source_from_document,
)


_build_knowledge_base_messages = lambda question, documents, web_results=None, *, enable_web_search=False, thinking_config=None: build_knowledge_base_messages(
    question,
    documents,
    web_results,
    enable_web_search=enable_web_search,
    thinking_config=thinking_config,
    format_web_search_context=_format_web_search_context,
    enforce_markdown_output=_enforce_markdown_output,
    apply_mode_instructions=_apply_mode_instructions,
    resolve_llm_config=_resolve_llm_config,
)


def _knowledge_web_search_module():
    return sys.modules[__name__]


_complete_knowledge_base_answer = build_complete_knowledge_base_answer(
    complete_llm_answer_resolver=lambda: getattr(
        _knowledge_web_search_module(),
        "_complete_llm_answer",
    ),
    prepare_web_search_tool_run=lambda *args, **kwargs: getattr(
        _knowledge_web_search_module(),
        "_prepare_web_search_tool_run",
    )(*args, **kwargs),
    status_from_web_search_state=_status_from_web_search_state,
    supports_keyword_argument=_supports_keyword_argument,
)


_WEB_SEARCH_ORCHESTRATION_COMPAT = build_web_search_orchestration_compat(
    _knowledge_web_search_module()
)


def __getattr__(name: str):
    if name in _WEB_SEARCH_ORCHESTRATION_COMPAT:
        return _WEB_SEARCH_ORCHESTRATION_COMPAT[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def _resolve_web_search_api_key(
    db: AsyncSession,
    user: SystemUser,
    *,
    enabled: bool,
    provider: str,
) -> str | None:
    return await resolve_knowledge_base_web_search_api_key(
        db,
        user,
        enabled=enabled,
        provider=provider,
        resolve_optional_user_api_credentials=resolve_optional_user_api_credentials,
    )


async def _load_scoped_chat_documents(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    allow_db_fallback: bool = True,
) -> list:
    module = sys.modules[__name__]
    return await _load_scoped_chat_documents_impl(
        payload,
        knowledge_base,
        current_workspace,
        db,
        allow_db_fallback=allow_db_fallback,
        resolve_request_scope_func=getattr(module, "_resolve_request_scope"),
        load_db_fallback_documents_func=getattr(module, "_load_db_fallback_documents"),
        rag_service_factory=getattr(module, "get_rag_service"),
        warning_logger=logger.warning,
    )


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseResponse]:
    return await list_workspace_knowledge_bases(db, workspace=current_workspace)


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    return await create_workspace_knowledge_base(
        db,
        payload=payload,
        user=current_user,
        workspace=current_workspace,
    )


@router.get("/{knowledge_base_id}/stats")
async def get_knowledge_base_stats(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """知识库统计信息（含文件夹入库状态）。"""
    return await build_knowledge_base_stats(db, knowledge_base=knowledge_base)


@router.get(
    "/{knowledge_base_id}/scope-options",
    response_model=KnowledgeScopeOptionsResponse,
    response_model_exclude_none=True,
)
async def get_knowledge_scope_options(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeScopeOptionsResponse:
    return await list_scope_options(db, knowledge_base_id=knowledge_base.id)


@router.post("/{knowledge_base_id}/build", response_model=KnowledgeBaseBuildResponse)
async def build_knowledge_base(
    payload: KnowledgeBaseBuildRequest,
    background_tasks: BackgroundTasks,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseBuildResponse:
    plan = await prepare_knowledge_base_build_request(
        db,
        payload=payload,
        user=current_user,
        workspace=current_workspace,
        knowledge_base=knowledge_base,
        bilibili_service_class=BilibiliService,
        asr_service_factory=ASRService,
        content_fetcher_class=ContentFetcher,
        rag_service_factory=_get_rag_service_for_build,
    )

    background_tasks.add_task(
        _run_scoped_build,
        **plan.task_kwargs,
    )

    return plan.response


@router.get("/{knowledge_base_id}/build/status/{task_id}")
async def get_build_status(
    task_id: str,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user_readonly),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取构建任务状态（按知识库校验）。"""
    return await get_build_status_payload(
        db,
        task_id=task_id,
        knowledge_base=knowledge_base,
    )


@router.post("/{knowledge_base_id}/search", response_model=KnowledgeBaseSearchResponse)
async def search_knowledge_base(
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseSearchResponse:
    return await search_knowledge_base_documents(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        workspace=current_workspace,
        rag_service_factory=get_rag_service,
    )


@router.post("/{knowledge_base_id}/chat", response_model=ChatResponse)
async def chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    return await answer_knowledge_base_chat(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        user=current_user,
        workspace=current_workspace,
        load_documents=_load_scoped_chat_documents,
        answer_from_documents=_answer_from_documents,
        resolve_llm_credentials=resolve_user_llm_credentials,
        global_config_resolver=_resolve_llm_config,
        resolve_web_search_api_key=_resolve_web_search_api_key,
        build_messages=_build_knowledge_base_messages,
        complete_answer=_complete_knowledge_base_answer,
        supports_keyword_argument=_supports_keyword_argument,
        record_usage=record_usage_event,
        source_from_document=_source_from_document,
        source_from_web_result=_source_from_web_result,
        web_search_failed_status_from_exception=(
            _web_search_failed_status_from_exception
        ),
        warning_logger=logger.warning,
    )


@router.post("/{knowledge_base_id}/chat/stream")
async def stream_chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    stream = await stream_knowledge_base_chat(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        user=current_user,
        workspace=current_workspace,
        load_documents=_load_scoped_chat_documents,
        answer_from_documents=_answer_from_documents,
        resolve_llm_credentials=resolve_user_llm_credentials,
        global_config_resolver=_resolve_llm_config,
        resolve_web_search_api_key=_resolve_web_search_api_key,
        build_messages=_build_knowledge_base_messages,
        prepare_web_search_with_heartbeats=getattr(
            _knowledge_web_search_module(),
            "_prepare_knowledge_base_web_search_with_heartbeats",
        ),
        append_no_more_tool_calls_instruction=(_append_no_more_tool_calls_instruction),
        stream_llm_events=_stream_llm_events,
        supports_keyword_argument=_supports_keyword_argument,
        encode_web_search_progress=_encode_web_search_progress,
        encode_thinking_delta=_encode_thinking_delta,
        source_from_document=_source_from_document,
        source_from_web_result=_source_from_web_result,
        web_search_failed_status_from_exception=(
            _web_search_failed_status_from_exception
        ),
        record_usage=record_usage_event,
        warning_logger=logger.warning,
    )
    return StreamingResponse(
        stream,
        media_type="text/plain; charset=utf-8",
    )


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除知识库及其相关数据。"""
    return await delete_knowledge_base_service(
        db,
        knowledge_base=knowledge_base,
        workspace=current_workspace,
        rag_service_factory=get_rag_service,
        supports_keyword_argument_func=_supports_keyword_argument,
        info_logger=logger.info,
        warning_logger=logger.warning,
    )
