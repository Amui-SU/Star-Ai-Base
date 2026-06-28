"""Chat routes for RAG question answering."""

import json
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    ChatRequest,
    ChatResponse,
    FavoriteFolder,
    FavoriteVideo,
    UserApiAccount,
    VideoCache,
)
from app.config import settings
from app.routers.system_auth import _get_current_admin_user
from app.services.api_credentials import (
    LLM_API_SOURCE_OFFICIAL,
    LLM_API_SOURCE_PERSONAL,
    normalize_llm_api_source,
    provider_defaults,
    resolve_user_llm_credentials,
)
from app.services.chat_config import (
    PROVIDER_ENV_FIELDS,
    PROVIDER_META,
    SUPPORTED_LLM_PROVIDERS,
    _current_default_llm_provider,
    _get_provider_thinking_config,
    _get_provider_thinking_template,
    _normalize_provider,
    _normalize_tavily_search_depth,
    _normalize_web_search_provider,
    _parse_thinking_config,
    _resolve_llm_config,
    _web_search_config_response,
    _write_env_values,
)
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
from app.services.chat_routing import (
    extract_keywords as _extract_keywords,
    filter_docs_by_keywords as _filter_docs_by_keywords,
    is_collection_intent as _is_collection_intent,
    is_general_question as _is_general_question,
    route_with_llm as _route_with_llm,
    route_with_rules as _route_with_rules,
)
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
    provider = _normalize_web_search_provider(body.provider)
    search_depth = _normalize_tavily_search_depth(body.tavily_search_depth)
    tavily_api_key = (body.tavily_api_key or "").strip()
    existing_tavily_key = settings.tavily_api_key.strip()
    if provider == "tavily" and not (tavily_api_key or existing_tavily_key):
        raise HTTPException(status_code=400, detail="Tavily API Key cannot be empty")

    updates = {
        "WEB_SEARCH_PROVIDER": provider,
        "WEB_SEARCH_FALLBACK_HTML": "true" if body.fallback_html else "false",
        "TAVILY_SEARCH_DEPTH": search_depth,
    }
    if tavily_api_key:
        updates["TAVILY_API_KEY"] = tavily_api_key

    _write_env_values(updates)
    settings.web_search_provider = provider
    settings.web_search_fallback_html = body.fallback_html
    settings.tavily_search_depth = search_depth
    if tavily_api_key:
        settings.tavily_api_key = tavily_api_key

    return _web_search_config_response(provider)


def _current_user_llm_source(
    user,
    *,
    has_personal: bool,
    has_official: bool,
) -> str:
    preferred = normalize_llm_api_source(
        getattr(user, "llm_api_source", None),
        default=None,
    )
    if preferred:
        return preferred
    if has_personal:
        return LLM_API_SOURCE_PERSONAL
    if has_official:
        return LLM_API_SOURCE_OFFICIAL
    return LLM_API_SOURCE_PERSONAL


async def _llm_config_response(current_user, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserApiAccount)
        .where(
            UserApiAccount.user_id == current_user.id,
            UserApiAccount.provider.in_(SUPPORTED_LLM_PROVIDERS),
        )
        .order_by(UserApiAccount.is_default.desc(), UserApiAccount.created_at.asc())
    )
    user_accounts = result.scalars().all()
    account_by_provider: dict[str, UserApiAccount] = {}
    enabled_account_by_provider: dict[str, UserApiAccount] = {}
    for account in user_accounts:
        account_by_provider.setdefault(account.provider, account)
        if account.enabled:
            enabled_account_by_provider.setdefault(account.provider, account)

    default_account = next(
        (
            account
            for account in user_accounts
            if account.enabled and account.is_default
        ),
        None,
    )
    if default_account is None:
        default_account = next(
            (account for account in user_accounts if account.enabled), None
        )
    official_config_by_provider = {
        provider: _resolve_llm_config(provider) for provider in PROVIDER_META
    }
    has_personal = default_account is not None
    has_official = any(
        bool((config.get("api_key") or "").strip())
        for config in official_config_by_provider.values()
    )
    current_api_source = _current_user_llm_source(
        current_user,
        has_personal=has_personal,
        has_official=has_official,
    )
    current_provider = (
        default_account.provider
        if current_api_source == LLM_API_SOURCE_PERSONAL and default_account
        else _current_default_llm_provider()
    )

    providers = []
    for provider, meta in PROVIDER_META.items():
        account = account_by_provider.get(provider)
        enabled_account = enabled_account_by_provider.get(provider)
        defaults = provider_defaults(provider)
        official_config = official_config_by_provider[provider]
        official_enabled = bool((official_config.get("api_key") or "").strip())
        personal_enabled = bool(enabled_account)
        selected_account = (
            enabled_account
            if current_api_source == LLM_API_SOURCE_PERSONAL
            else account
        )
        if current_api_source == LLM_API_SOURCE_OFFICIAL:
            model = official_config["model"]
            base_url = official_config["base_url"]
            thinking_config = official_config["thinking_config"]
            enabled = official_enabled
        else:
            model = selected_account.model if selected_account else defaults.model
            base_url = (
                selected_account.base_url if selected_account else defaults.base_url
            )
            thinking_config = (
                selected_account.thinking_config if selected_account else {}
            )
            enabled = personal_enabled
        providers.append(
            {
                "provider": provider,
                "label": meta["label"],
                "enabled": enabled,
                "official_enabled": official_enabled,
                "personal_enabled": personal_enabled,
                "model": model,
                "base_url": base_url,
                "thinking_config": thinking_config,
                "thinking_template": _get_provider_thinking_template(provider),
            }
        )
    return {
        "current_provider": current_provider,
        "current_api_source": current_api_source,
        "providers": providers,
    }


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
    provider = _normalize_provider(body.provider)
    env_fields = PROVIDER_ENV_FIELDS.get(provider)
    if not env_fields:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {provider}")

    current = _resolve_llm_config(provider)
    api_key = (body.api_key or "").strip() or current["api_key"]
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    thinking_mode = body.thinking_mode.strip().lower()
    if thinking_mode not in {"off", "standard", "custom"}:
        raise HTTPException(status_code=400, detail="不支持的思考配置模式")
    if thinking_mode == "off":
        thinking_config = {}
    elif thinking_mode == "standard":
        thinking_config = _get_provider_thinking_template(provider)
        if not thinking_config:
            raise HTTPException(
                status_code=400,
                detail="该提供商没有通用标准模板，请使用自定义 JSON",
            )
    else:
        thinking_config = _parse_thinking_config(body.thinking_config)
        if not thinking_config:
            raise HTTPException(status_code=400, detail="自定义思考配置不能为空")

    base_url = (body.base_url or "").strip() or current["base_url"]
    model = (body.model or "").strip() or current["model"]
    pending_config = {
        "provider": provider,
        "provider_label": current["provider_label"],
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "thinking_config": thinking_config,
    }
    latency_ms = _verify_provider_configuration(pending_config)

    updates = {
        "LLM_PROVIDER": provider,
        env_fields["api_key"]: api_key,
        env_fields["base_url"]: base_url,
        env_fields["model"]: model,
        env_fields["thinking_config"]: json.dumps(
            thinking_config,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }

    _write_env_values(updates)

    try:
        reset_rag_service()
    except Exception as e:
        logger.warning(f"重置 RAG 服务失败，将在下次重启后生效: {e}")

    llm_config = _resolve_llm_config(provider)
    logger.info(f"已保存 LLM 配置: {provider} / model={llm_config['model']}")
    return {
        "ok": True,
        "current_provider": provider,
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
        "thinking_config": llm_config["thinking_config"],
        "thinking_template": _get_provider_thinking_template(provider),
        "verified": True,
        "latency_ms": latency_ms,
    }


@router.post("/llm/config")
async def set_llm_config(
    body: LLMProviderUpdateRequest,
    _current_admin=Depends(_require_current_admin_user),
):
    """切换当前问答模型提供方"""
    llm_config = _resolve_llm_config(body.provider)
    if not llm_config["api_key"]:
        raise HTTPException(
            status_code=400,
            detail=f"{llm_config['provider_label']} API Key 未配置，请先在 .env.local 中配置后重启后端。",
        )
    _write_env_values({"LLM_PROVIDER": llm_config["provider"]})
    logger.info(
        f"已切换 LLM 提供方: {llm_config['provider']} / model={llm_config['model']}"
    )
    return {
        "ok": True,
        "current_provider": llm_config["provider"],
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
    }


@router.get("/health/llm")
async def llm_health_check(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM 连通性检查"""
    try:
        credential = await resolve_user_llm_credentials(
            db,
            current_user,
            global_config_resolver=_resolve_llm_config,
        )
        llm_config = credential.to_llm_config()
    except HTTPException as exc:
        fallback_config = _resolve_llm_config()
        detail = exc.detail
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        return {
            "status": "down",
            "message": message or "未配置 LLM API Key",
            "latency_ms": None,
            "model": fallback_config["model"],
            "provider": fallback_config["provider"],
        }

    start = time.perf_counter()
    try:
        client = _get_llm_client(llm_config)
        # 最小化探活请求，避免额外开销
        client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "status": "ok",
            "message": "模型服务可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(f"LLM 健康检查失败: {e}")
        return {
            "status": "down",
            "message": str(e) or "模型服务不可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }


def _get_llm_client(llm_config: Optional[Dict[str, str]] = None) -> OpenAI:
    """获取 LLM 客户端"""
    cfg = llm_config or _resolve_llm_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 LLM API Key")
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=30.0,
        max_retries=2,
    )


_create_chat_completion_async = create_chat_completion_async
_is_llm_connection_error = is_llm_connection_error
_build_llm_unavailable_answer = build_llm_unavailable_answer


def _log_final_payload(route: str, messages: list[dict], sources: list[dict]) -> None:
    """记录最终发送给 LLM 的内容与来源"""
    logger.info(f"最终路由: {route}")
    logger.info(f"最终消息: {messages}")
    logger.info(f"最终来源数量: {len(sources)}")


_build_thinking_completion_options = build_thinking_completion_options


_verify_provider_configuration = lambda llm_config: verify_provider_configuration(
    llm_config,
    get_llm_client=_get_llm_client,
)


_encode_thinking_delta = lambda content: encode_thinking_delta(
    content, THINKING_DELTA_MARKER
)


_stream_llm_events = lambda messages, llm_config=None: stream_llm_events(
    messages,
    llm_config,
    resolve_llm_config=_resolve_llm_config,
    get_llm_client=_get_llm_client,
)


_complete_llm_answer = lambda messages, llm_config=None: complete_llm_answer(
    messages,
    llm_config,
    resolve_llm_config=_resolve_llm_config,
    get_llm_client=_get_llm_client,
)


_complete_llm_answer_with_tools = lambda messages, *, tools, tool_handlers, max_tool_calls=2: complete_llm_answer_with_tools(
    messages,
    tools=tools,
    tool_handlers=tool_handlers,
    max_tool_calls=max_tool_calls,
    resolve_llm_config=_resolve_llm_config,
    get_llm_client=_get_llm_client,
)


_prepare_llm_messages_with_tools = lambda messages, *, tools, tool_handlers, max_tool_calls=2, after_tool_messages=None, llm_config=None: prepare_llm_messages_with_tools(
    messages,
    tools=tools,
    tool_handlers=tool_handlers,
    max_tool_calls=max_tool_calls,
    after_tool_messages=after_tool_messages,
    llm_config=llm_config,
    resolve_llm_config=_resolve_llm_config,
    get_llm_client=_get_llm_client,
)


async def _is_related_to_collection(
    db: AsyncSession, folder_ids: List[int], question: str
) -> bool:
    """判断问题是否与收藏夹内容有关"""
    if not folder_ids:
        return False
    keywords = _extract_keywords(question)
    if not keywords:
        return False
    like_conds = []
    for kw in keywords:
        pattern = f"%{kw}%"
        like_conds.append(VideoCache.title.ilike(pattern))
        like_conds.append(VideoCache.description.ilike(pattern))
        like_conds.append(VideoCache.content.ilike(pattern))
    stmt = (
        select(func.count())
        .select_from(VideoCache)
        .join(FavoriteVideo, FavoriteVideo.bvid == VideoCache.bvid)
        .where(FavoriteVideo.folder_id.in_(folder_ids))
        .where(or_(*like_conds))
    )
    count = await db.scalar(stmt)
    return (count or 0) > 0


async def _get_folder_ids_for_session(
    db: AsyncSession, session_id: str, media_ids: Optional[List[int]]
) -> List[int]:
    """根据 session 和 media_id 获取内部 folder_id（支持跨 session 查找同用户数据）"""
    from app.models import UserSession

    # 1. 尝试获取当前 session 的 mid
    mid_result = await db.execute(
        select(UserSession.bili_mid).where(UserSession.session_id == session_id)
    )
    mid = mid_result.scalar()
    target_session_ids = [session_id]
    if mid:
        # 查找该用户所有的 Session ID
        sessions_result = await db.execute(
            select(UserSession.session_id).where(UserSession.bili_mid == mid)
        )
        target_session_ids = [row[0] for row in sessions_result.fetchall()]
    # 构建查询：按 media_id 去重，只保留最新的一条
    stmt = (
        select(FavoriteFolder.id, FavoriteFolder.media_id, FavoriteFolder.updated_at)
        .where(FavoriteFolder.session_id.in_(target_session_ids))
        .order_by(FavoriteFolder.updated_at.desc())
    )
    if media_ids:
        stmt = stmt.where(FavoriteFolder.media_id.in_(media_ids))
    rows = await db.execute(stmt)
    dedup: dict[int, int] = {}
    for folder_id, media_id, _updated_at in rows.fetchall():
        if media_id not in dedup:
            dedup[media_id] = folder_id
    return list(dedup.values())


async def _get_bvids_by_folder_ids(
    db: AsyncSession, folder_ids: List[int]
) -> List[str]:
    """获取指定收藏夹的视频 BV 列表"""
    if not folder_ids:
        return []
    rows = await db.execute(
        select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id.in_(folder_ids))
    )
    bvids = []
    seen = set()
    for (bvid,) in rows.fetchall():
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        bvids.append(bvid)
    return bvids


async def _get_video_context(
    db: AsyncSession,
    folder_ids: List[int],
    include_content: bool = False,
    limit: Optional[int] = 50,
) -> tuple[str, List[dict]]:
    """获取视频上下文信息"""
    if not folder_ids:
        return "", []
    # 查询视频信息
    query = (
        select(
            FavoriteFolder.title.label("folder_title"),
            VideoCache.bvid,
            VideoCache.title,
            VideoCache.description,
            VideoCache.content if include_content else VideoCache.description,
        )
        .join(FavoriteVideo, FavoriteVideo.folder_id == FavoriteFolder.id)
        .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid, isouter=True)
        .where(FavoriteFolder.id.in_(folder_ids))
    )
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    records = result.fetchall()
    if not records:
        return "", []
    # 按收藏夹分组（对 bvid 去重，避免同一视频重复出现）
    grouped = {}
    sources = []
    seen_bvids = set()
    for folder_title, bvid, title, desc, content in records:
        if not bvid or not title:
            continue
        if bvid in seen_bvids:
            continue
        folder_name = folder_title or "默认收藏夹"
        if folder_name not in grouped:
            grouped[folder_name] = []
        video_info = f"- 《{title}》"
        if include_content and content:
            video_info += f"\n  摘要: {content}"
        elif desc:
            short_desc = desc[:100] + "..." if len(desc) > 100 else desc
            video_info += f" ({short_desc})"
        grouped[folder_name].append(video_info)
        seen_bvids.add(bvid)
        sources.append(
            {
                "bvid": bvid,
                "title": title,
                "url": f"https://www.bilibili.com/video/{bvid}",
            }
        )
    # 构建上下文文本
    context_parts = [
        f"【{folder_name}】\n" + "\n".join(videos)
        for folder_name, videos in grouped.items()
    ]
    context = "\n\n".join(context_parts)
    return context, sources


async def _get_video_titles_context(
    db: AsyncSession, folder_ids: List[int], limit: int = 50
) -> str:
    """获取收藏夹名称与视频标题（用于引导问题）"""
    if not folder_ids:
        return ""
    query = (
        select(
            FavoriteFolder.title.label("folder_title"),
            VideoCache.bvid,
            VideoCache.title,
        )
        .join(FavoriteVideo, FavoriteVideo.folder_id == FavoriteFolder.id)
        .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid, isouter=True)
        .where(FavoriteFolder.id.in_(folder_ids))
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.fetchall()
    if not records:
        return ""
    grouped = {}
    seen_bvids = set()
    for folder_title, bvid, title in records:
        if not title or not bvid:
            continue
        if bvid in seen_bvids:
            continue
        seen_bvids.add(bvid)
        folder_name = folder_title or "默认收藏夹"
        grouped.setdefault(folder_name, []).append(f"- 《{title}》")
    context_parts = [
        f"【{folder_name}】\n" + "\n".join(videos)
        for folder_name, videos in grouped.items()
    ]
    return "\n\n".join(context_parts)


async def _prepare_messages(
    request: ChatRequest, db: AsyncSession
) -> tuple[list[dict], List[dict], str]:
    """准备 LLM 消息与来源信息"""
    question = request.question.strip()
    rag = get_rag_service()
    folder_ids = []
    if request.session_id:
        folder_ids = await _get_folder_ids_for_session(
            db, request.session_id, request.folder_ids
        )
        logger.info(f"Session: {request.session_id}, 关联 FolderIDs: {folder_ids}")
    bvids = await _get_bvids_by_folder_ids(db, folder_ids) if folder_ids else []
    has_data = len(bvids) > 0
    is_collection_intent = _is_collection_intent(question)
    is_general = _is_general_question(question)
    if request.folder_ids:
        is_collection_intent = True
    # 1) LLM 路由优先，失败时降级规则路由
    logger.info(
        f"路由输入: question={question} folder_ids={folder_ids} has_data={has_data} is_collection_intent={is_collection_intent}"
    )
    route, route_raw = _route_with_llm(
        question,
        resolve_llm_config=_resolve_llm_config,
        get_llm_client=_get_llm_client,
        log_warning=logger.warning,
    )
    route_source = "LLM"
    related: Optional[bool] = None
    if not route:
        related = await _is_related_to_collection(db, folder_ids, question)
        route = _route_with_rules(question, is_collection_intent, related)
        route_source = "RULE"
    logger.info(f"路由策略: {route_source} => {route}")
    # 纠偏
    if is_general:
        route = "direct"
    # 2) 无数据时处理
    if not has_data:
        if is_collection_intent:
            context, sources = await _get_video_context(
                db, folder_ids, include_content=False, limit=50
            )
            if not context:
                context = "（暂无已入库的视频信息，请提醒用户可能需要先进行入库操作）"
            messages = _build_fallback_messages(context, question)
            return messages, sources, question
        messages = _build_direct_messages(question)
        return messages, [], question
    # 3) 直接回答
    if route == "direct":
        title_context = await _get_video_titles_context(db, folder_ids, limit=50)
        messages = (
            _build_direct_messages_with_context(title_context, question)
            if title_context
            else _build_direct_messages(question)
        )
        return messages, [], question
    # 4) 列表类问题
    if route == "db_list":
        if related is None:
            related = await _is_related_to_collection(db, folder_ids, question)
        if not related and not is_collection_intent:
            return _build_direct_messages(question), [], question
        context, sources = await _get_video_context(
            db, folder_ids, include_content=False, limit=50
        )
        if not context:
            return (
                _build_fallback_messages("（暂无信息，请入库）", question),
                sources,
                question,
            )
        return _build_db_list_messages(context, question), sources, question
    # 5) 总结类问题
    if route == "db_content":
        if related is None:
            related = await _is_related_to_collection(db, folder_ids, question)
        if not related and not is_collection_intent:
            return _build_direct_messages(question), [], question
        context, sources = await _get_video_context(
            db, folder_ids, include_content=True, limit=None
        )
        if not context:
            return (
                _build_fallback_messages("（暂无信息，请入库）", question),
                sources,
                question,
            )
        return _build_db_summary_messages(context, question), sources, question
    # 6) 检查相关性
    if related is None:
        related = await _is_related_to_collection(db, folder_ids, question)
    if not related and not is_collection_intent:
        return _build_direct_messages(question), [], question
    # 7) 向量检索
    docs = []
    try:
        docs = rag.search(question, k=5, bvids=bvids if bvids else None)
    except Exception as e:
        logger.warning(f"向量检索失败: {e}")
    if docs:
        filtered_docs = _filter_docs_by_keywords(docs, question)
        docs = filtered_docs if filtered_docs else docs
        context_parts, sources, seen_bvids = [], [], set()
        for doc in docs:
            bvid, title, content = (
                doc.metadata.get("bvid", ""),
                doc.metadata.get("title", ""),
                doc.page_content.strip(),
            )
            if content:
                context_parts.append(f"【{title}】\n{content}")
            if bvid and bvid not in seen_bvids:
                seen_bvids.add(bvid)
                sources.append(
                    {
                        "bvid": bvid,
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                    }
                )
        return (
            _build_rag_messages("\n\n---\n\n".join(context_parts), question),
            sources,
            question,
        )
    # 兜底
    context, sources = await _get_video_context(
        db, folder_ids, include_content=False, limit=50
    )
    return (
        _build_fallback_messages(context or "（暂无入库信息）", question),
        sources,
        question,
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
        llm_config = _resolve_llm_config()
        messages, sources, _ = await _prepare_messages(request, db)
        messages = _enforce_markdown_output(messages)
        messages = _apply_mode_instructions(
            messages,
            bool(llm_config["thinking_config"]),
        )
        client = _get_llm_client(llm_config)
        try:
            response = client.chat.completions.create(
                model=llm_config["model"],
                messages=messages,
                temperature=0.5,
                **_build_thinking_completion_options(llm_config),
            )
            message = response.choices[0].message
            raw_answer = message.content or ""
            reasoning = getattr(message, "reasoning_content", None)
            thinking, answer = _extract_thinking_and_answer(raw_answer, reasoning)
            return ChatResponse(
                answer=answer, sources=sources[:5], thinking=thinking or None
            )
        except Exception as e:
            if _is_llm_connection_error(e):
                logger.warning(f"模型连接异常，使用降级回答: {e}")
                return ChatResponse(
                    answer=_build_llm_unavailable_answer(),
                    sources=sources[:5],
                    thinking=None,
                )
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")


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
        llm_config = _resolve_llm_config()
        messages, sources, _ = await _prepare_messages(request, db)
        messages = _enforce_markdown_output(messages)
        messages = _apply_mode_instructions(
            messages,
            bool(llm_config["thinking_config"]),
        )

        def generate():
            thinking_parts: list[str] = []
            try:
                for event_type, content in _stream_llm_events(messages):
                    if event_type == "thinking":
                        thinking_parts.append(content)
                        yield _encode_thinking_delta(content)
                    else:
                        yield content
            except Exception as e:
                if _is_llm_connection_error(e):
                    logger.warning(f"流式模型连接异常，使用降级回答: {e}")
                    yield _build_llm_unavailable_answer()
                else:
                    raise
            if thinking_parts:
                yield f"\n[[THINKING_JSON]]{json.dumps(''.join(thinking_parts), ensure_ascii=False)}"
            yield f"\n[[SOURCES_JSON]]{json.dumps(sources, ensure_ascii=False)}"

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"流式问答失败: {str(e)}")


@router.post("/search")
async def search_videos(query: Optional[str] = None, k: int = 5):
    """搜索相关视频片段"""
    _raise_legacy_scoped_api_required()
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        rag = get_rag_service()
        docs = rag.search(query, k=k)
        results, seen_bvids = [], set()
        for doc in docs:
            bvid = doc.metadata.get("bvid", "")
            if bvid in seen_bvids:
                continue
            seen_bvids.add(bvid)
            results.append(
                {
                    "bvid": bvid,
                    "title": doc.metadata.get("title", ""),
                    "url": doc.metadata.get("url", ""),
                    "content_preview": (
                        doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content
                    ),
                }
            )
        return {"results": results}
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
