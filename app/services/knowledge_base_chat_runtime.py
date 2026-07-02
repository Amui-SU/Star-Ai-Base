"""Router dependency assembly for knowledge-base chat endpoints."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, SystemUser, Workspace
from app.schemas.chat import ChatResponse
from app.schemas.knowledge_base import KnowledgeBaseChatRequest
from app.services.knowledge_base_chat import answer_knowledge_base_chat
from app.services.knowledge_base_chat_stream import stream_knowledge_base_chat


async def answer_knowledge_base_chat_from_router(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    user: SystemUser,
    workspace: Workspace,
    router_module: Any,
    warning_logger,
) -> ChatResponse:
    return await answer_knowledge_base_chat(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        user=user,
        workspace=workspace,
        load_documents=router_module._load_scoped_chat_documents,
        answer_from_documents=router_module._answer_from_documents,
        resolve_llm_credentials=router_module.resolve_user_llm_credentials,
        global_config_resolver=router_module._resolve_llm_config,
        resolve_web_search_api_key=router_module._resolve_web_search_api_key,
        build_messages=router_module._build_knowledge_base_messages,
        complete_answer=router_module._complete_knowledge_base_answer,
        supports_keyword_argument=router_module._supports_keyword_argument,
        record_usage=router_module.record_usage_event,
        source_from_document=router_module._source_from_document,
        source_from_web_result=router_module._source_from_web_result,
        web_search_failed_status_from_exception=(
            router_module._web_search_failed_status_from_exception
        ),
        warning_logger=warning_logger,
    )


async def stream_knowledge_base_chat_from_router(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase,
    user: SystemUser,
    workspace: Workspace,
    router_module: Any,
    warning_logger,
):
    return await stream_knowledge_base_chat(
        db,
        payload=payload,
        knowledge_base=knowledge_base,
        user=user,
        workspace=workspace,
        load_documents=router_module._load_scoped_chat_documents,
        answer_from_documents=router_module._answer_from_documents,
        resolve_llm_credentials=router_module.resolve_user_llm_credentials,
        global_config_resolver=router_module._resolve_llm_config,
        resolve_web_search_api_key=router_module._resolve_web_search_api_key,
        build_messages=router_module._build_knowledge_base_messages,
        prepare_web_search_with_heartbeats=(
            router_module._prepare_knowledge_base_web_search_with_heartbeats
        ),
        append_no_more_tool_calls_instruction=(
            router_module._append_no_more_tool_calls_instruction
        ),
        stream_llm_events=router_module._stream_llm_events,
        supports_keyword_argument=router_module._supports_keyword_argument,
        encode_web_search_progress=router_module._encode_web_search_progress,
        encode_thinking_delta=router_module._encode_thinking_delta,
        source_from_document=router_module._source_from_document,
        source_from_web_result=router_module._source_from_web_result,
        web_search_failed_status_from_exception=(
            router_module._web_search_failed_status_from_exception
        ),
        record_usage=router_module.record_usage_event,
        warning_logger=warning_logger,
    )
