"""Chat routes for RAG question answering."""

import sys
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models import UserApiAccount
from app.schemas.chat import ChatRequest, ChatResponse
from app.config import settings
from app.services.system_auth_admin import (
    get_current_admin_user as _get_current_admin_user,
)
from app.services.api_credentials import (
    normalize_llm_api_source,
    resolve_user_llm_credentials,
)
from app.services.chat_config import (
    PROVIDER_META,
    _current_default_llm_provider,
    _get_provider_thinking_config,
    _get_provider_thinking_template,
    _normalize_web_search_provider,
    _parse_thinking_config,
    _resolve_llm_config,
    _web_search_config_response,
    _write_env_values,
    llm_config_response,
    save_global_llm_provider_config,
    save_global_web_search_config,
    set_global_llm_provider,
)
from app.services.chat_health import llm_health_response
from app.services.llm_tool_calls import (
    LLMToolRunResult,
    append_no_more_tool_calls_instruction as _append_no_more_tool_calls_instruction,
    extract_thinking_and_answer as _extract_thinking_and_answer,
    message_to_openai_dict as _message_to_openai_dict,
    parse_tool_arguments as _parse_tool_arguments,
)
from app.services.chat_messages import (
    apply_mode_instructions as _apply_mode_instructions,
    build_db_list_messages as _build_db_list_messages,
    build_db_summary_messages as _build_db_summary_messages,
    build_direct_messages as _build_direct_messages,
    build_direct_messages_with_context as _build_direct_messages_with_context,
    build_fallback_messages as _build_fallback_messages,
    build_overview_messages as _build_overview_messages,
    build_rag_messages as _build_rag_messages,
    enforce_markdown_output as _enforce_markdown_output,
)
from app.services.chat_completion import (
    build_llm_unavailable_answer,
    build_completion_request_options,
    build_thinking_completion_options,
    complete_llm_answer,
    complete_llm_answer_with_tools,
    create_chat_completion_async,
    encode_thinking_delta,
    is_llm_connection_error,
    prepare_llm_messages_with_tools,
    stream_llm_events,
    verify_provider_configuration,
)
from app.services.chat_router_adapters import (
    build_chat_router_adapters,
)
from app.services.chat_routing import (
    filter_docs_by_keywords as _filter_docs_by_keywords,
    is_collection_intent as _is_collection_intent,
    is_general_question as _is_general_question,
    route_with_llm as _route_with_llm,
    route_with_rules as _route_with_rules,
)
from app.services.chat_video_context import (
    get_bvids_by_folder_ids as _get_bvids_by_folder_ids,
    get_folder_ids_for_session as _get_folder_ids_for_session,
    get_video_context as _get_video_context,
    get_video_titles_context as _get_video_titles_context,
    is_related_to_collection as _is_related_to_collection,
)
from app.services.chat_message_preparation import prepare_chat_messages
from app.services.chat_route_runtime import (
    answer_legacy_chat_from_router,
    stream_legacy_chat_from_router,
)
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.llm_errors import classify_upstream_error
from app.services.rag_runtime import get_rag_service, reset_rag_service

router = APIRouter(prefix="/chat", tags=["对话"])
LEGACY_SCOPED_API_DETAIL = "旧全局接口已禁用，请使用 /knowledge-bases/* 范围化 API。"


def _raise_legacy_scoped_api_required() -> None:
    raise HTTPException(status_code=410, detail=LEGACY_SCOPED_API_DETAIL)


async def _require_current_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _get_current_admin_user(request, db)


THINKING_DELTA_MARKER = "[[THINKING_DELTA]]"


class LLMProviderUpdateRequest(BaseModel):
    provider: str


class LLMSourceUpdateRequest(BaseModel):
    api_source: str


class LLMProviderConfigRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_mode: str = "off"
    thinking_config: Optional[dict] = None


class WebSearchConfigRequest(BaseModel):
    provider: str = "auto"
    tavily_api_key: Optional[str] = None
    fallback_html: bool = True
    tavily_search_depth: str = "basic"


async def _user_has_tavily_account(db: AsyncSession, user) -> bool:
    result = await db.execute(
        select(UserApiAccount.id)
        .where(
            UserApiAccount.user_id == user.id,
            UserApiAccount.provider == "tavily",
            UserApiAccount.enabled.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


@router.get("/web-search/config")
async def get_web_search_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return web search settings without exposing saved API keys."""
    provider = _normalize_web_search_provider(settings.web_search_provider)
    return _web_search_config_response(
        provider,
        tavily_configured=bool(settings.tavily_api_key.strip())
        or await _user_has_tavily_account(db, current_user),
    )


@router.post("/web-search/config")
async def save_web_search_config(
    body: WebSearchConfigRequest,
    _current_admin=Depends(_require_current_admin_user),
):
    """Persist web search configuration to .env.local without echoing secrets."""
    return save_global_web_search_config(
        provider=body.provider,
        tavily_api_key=body.tavily_api_key,
        fallback_html=body.fallback_html,
        tavily_search_depth=body.tavily_search_depth,
        env_writer=_write_env_values,
    )


_llm_config_response = llm_config_response


@router.get("/llm/config")
async def get_llm_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前模型配置（不返回密钥）"""
    return await _llm_config_response(current_user, db)


@router.post("/llm/source")
async def set_llm_source(
    body: LLMSourceUpdateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换当前用户聊天使用官方通道或个人密钥。"""
    current_user.llm_api_source = normalize_llm_api_source(body.api_source)
    await db.commit()
    await db.refresh(current_user)
    return await _llm_config_response(current_user, db)


@router.post("/llm/provider-config")
async def save_llm_provider_config(
    body: LLMProviderConfigRequest,
    _current_admin=Depends(_require_current_admin_user),
):
    """验证并保存模型提供方配置到 .env.local。"""
    return save_global_llm_provider_config(
        provider=body.provider,
        api_key=body.api_key,
        base_url=body.base_url,
        model=body.model,
        thinking_mode=body.thinking_mode,
        thinking_config=body.thinking_config,
        verifier=_verify_provider_configuration,
        resolve_llm_config=_resolve_llm_config,
        get_provider_thinking_template=_get_provider_thinking_template,
        parse_thinking_config=_parse_thinking_config,
        env_writer=_write_env_values,
        reset_rag=reset_rag_service,
        warning_logger=logger.warning,
        info_logger=logger.info,
    )


@router.post("/llm/config")
async def set_llm_config(
    body: LLMProviderUpdateRequest,
    _current_admin=Depends(_require_current_admin_user),
):
    """切换当前问答模型提供方"""
    return set_global_llm_provider(
        body.provider,
        env_writer=_write_env_values,
        resolve_llm_config=_resolve_llm_config,
        info_logger=logger.info,
    )


@router.get("/health/llm")
async def llm_health_check(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM 连通性检查"""
    return await llm_health_response(
        db,
        current_user,
        resolve_llm_credentials=resolve_user_llm_credentials,
        global_config_resolver=_resolve_llm_config,
        get_llm_client=_get_llm_client,
        warning_logger=logger.warning,
    )


_create_chat_completion_async = create_chat_completion_async
_is_llm_connection_error = is_llm_connection_error
_build_llm_unavailable_answer = build_llm_unavailable_answer


def _chat_router_module():
    return sys.modules[__name__]


def _log_final_payload(route: str, messages: list[dict], sources: list[dict]) -> None:
    """记录最终发送给 LLM 的内容与来源"""
    logger.info(f"最终路由: {route}")
    logger.info(f"最终消息: {messages}")
    logger.info(f"最终来源数量: {len(sources)}")


_build_thinking_completion_options = build_thinking_completion_options
_build_completion_request_options = build_completion_request_options


_verify_provider_configuration = lambda llm_config: verify_provider_configuration(
    llm_config,
    get_llm_client=_get_llm_client,
)


_CHAT_ROUTER_ADAPTERS = build_chat_router_adapters(
    _chat_router_module(),
    stream_llm_events=stream_llm_events,
    complete_llm_answer=complete_llm_answer,
    complete_llm_answer_with_tools=complete_llm_answer_with_tools,
    prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
    encode_thinking_delta=encode_thinking_delta,
    thinking_delta_marker=THINKING_DELTA_MARKER,
)

_encode_thinking_delta = _CHAT_ROUTER_ADAPTERS["_encode_thinking_delta"]
_stream_llm_events = _CHAT_ROUTER_ADAPTERS["_stream_llm_events"]
_complete_llm_answer = _CHAT_ROUTER_ADAPTERS["_complete_llm_answer"]
_complete_llm_answer_with_tools = _CHAT_ROUTER_ADAPTERS[
    "_complete_llm_answer_with_tools"
]
_prepare_llm_messages_with_tools = _CHAT_ROUTER_ADAPTERS[
    "_prepare_llm_messages_with_tools"
]


async def _prepare_messages(
    request: ChatRequest, db: AsyncSession
) -> tuple[list[dict], List[dict], str]:
    """准备 LLM 消息与来源信息"""
    return await prepare_chat_messages(
        request,
        db,
        get_folder_ids=_get_folder_ids_for_session,
        get_bvids=_get_bvids_by_folder_ids,
        check_related=_is_related_to_collection,
        load_video_context=_get_video_context,
        load_video_titles_context=_get_video_titles_context,
        get_rag=get_rag_service,
        collection_intent_detector=_is_collection_intent,
        general_question_detector=_is_general_question,
        llm_router=_route_with_llm,
        rules_router=_route_with_rules,
        doc_filter=_filter_docs_by_keywords,
        build_fallback=_build_fallback_messages,
        build_direct=_build_direct_messages,
        build_direct_with_context=_build_direct_messages_with_context,
        build_db_list=_build_db_list_messages,
        build_db_summary=_build_db_summary_messages,
        build_rag=_build_rag_messages,
        resolve_llm_config=_resolve_llm_config,
        get_llm_client=_get_llm_client,
        log_info=logger.info,
        log_warning=logger.warning,
    )


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: Optional[ChatRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """智能问答"""
    _raise_legacy_scoped_api_required()
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        return await answer_legacy_chat_from_router(
            request,
            db,
            router_module=_chat_router_module(),
            warning_logger=logger.warning,
        )
    except HTTPException:
        raise
    except Exception as exc:
        failure = classify_upstream_error(exc)
        logger.error(failure.log_message("问答失败"))
        raise HTTPException(status_code=500, detail=failure.detail()) from exc


@router.post("/ask/stream")
async def ask_question_stream(
    request: Optional[ChatRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """流式问答"""
    _raise_legacy_scoped_api_required()
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        stream = await stream_legacy_chat_from_router(
            request,
            db,
            router_module=_chat_router_module(),
            warning_logger=logger.warning,
        )
        return StreamingResponse(stream, media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as exc:
        failure = classify_upstream_error(exc)
        logger.error(failure.log_message("流式问答失败"))
        raise HTTPException(status_code=500, detail=failure.detail()) from exc


@router.post("/search")
async def search_videos(query: Optional[str] = None, k: int = 5):
    """搜索相关视频片段"""
    _raise_legacy_scoped_api_required()
