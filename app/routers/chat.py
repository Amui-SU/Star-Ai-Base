"""Chat routes for RAG question answering."""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models import UserApiAccount
from app.config import settings
from app.services.system_auth_admin import (
    get_current_admin_user as _get_current_admin_user,
)
from app.services.api_credentials import (
    normalize_llm_api_source,
    resolve_user_llm_credentials,
)
from app.services.chat_config import (
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
from app.services.chat_completion import verify_provider_configuration
from app.services.legacy_api import raise_legacy_api_gone
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.rag_runtime import reset_rag_service

router = APIRouter(prefix="/chat", tags=["对话"])


async def _require_current_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _get_current_admin_user(request, db)


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


_verify_provider_configuration = lambda llm_config: verify_provider_configuration(
    llm_config,
    get_llm_client=_get_llm_client,
)


@router.post("/ask")
async def ask_question():
    """智能问答（已禁用）"""
    raise_legacy_api_gone()


@router.post("/ask/stream")
async def ask_question_stream():
    """流式问答（已禁用）"""
    raise_legacy_api_gone()


@router.post("/search")
async def search_videos(query: Optional[str] = None, k: int = 5):
    """搜索相关视频片段（已禁用）"""
    raise_legacy_api_gone()
