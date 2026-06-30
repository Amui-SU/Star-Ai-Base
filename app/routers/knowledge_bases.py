import json
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
    get_knowledge_base_for_user_readonly,
)
from app.models import (
    ChatResponse,
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    KnowledgeBase,
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    KnowledgeScopeOptionsResponse,
    SourceBinding,
    SourceCredential,
    SystemUser,
    VideoTitleOverride,
    Workspace,
)
from app.services.ingestion_tasks import (
    create_ingestion_task,
)
from app.services.rag_runtime import get_rag_service
from app.services.knowledge_base_build_tasks import (
    get_build_status_payload,
    run_scoped_build as _run_scoped_build,
)
from app.services.knowledge_base_documents import (
    load_db_fallback_documents as _load_db_fallback_documents,
    load_scoped_chat_documents as _load_scoped_chat_documents_impl,
    resolve_request_scope as _resolve_request_scope,
)
from app.services.knowledge_base_presenters import (
    dedupe_ints as _dedupe_ints,
    dedupe_strings as _dedupe_strings,
    response_from_knowledge_base as _response,
    search_result_from_document as _search_result,
    source_from_document as _source_from_document,
    supports_keyword_argument as _supports_keyword_argument,
)
from app.services.knowledge_base_messages import (
    answer_from_documents,
    build_knowledge_base_messages,
)
from app.services.chat_messages import (
    apply_mode_instructions as _apply_mode_instructions,
    enforce_markdown_output as _enforce_markdown_output,
)
from app.routers.chat import (
    _append_no_more_tool_calls_instruction,
    _complete_llm_answer,
    _encode_thinking_delta,
    _prepare_llm_messages_with_tools,
    _resolve_llm_config,
    _stream_llm_events,
)
from app.security import decrypt_text
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
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
from app.services.knowledge_web_search_orchestration import (
    FETCH_WEB_PAGE_CONTEXT_CHARS as _FETCH_WEB_PAGE_CONTEXT_CHARS,
    MAX_FETCH_WEB_PAGE_CALLS as _MAX_FETCH_WEB_PAGE_CALLS,
    WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS as _WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS,
    WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS as _WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS,
    execute_fetch_web_page_tool as _execute_fetch_web_page_tool_impl,
    execute_web_search_tool as _execute_web_search_tool_impl,
    prepare_knowledge_base_web_search_with_heartbeats as _prepare_knowledge_base_web_search_with_heartbeats_impl,
    prepare_web_search_tool_run as _prepare_web_search_tool_run_impl,
    run_initial_web_search as _run_initial_web_search_impl,
)
from app.services.api_credentials import (
    record_usage_event,
    resolve_optional_user_api_credentials,
    resolve_user_llm_credentials,
)
from app.services.web_search import fetch_web_page, search_web

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

WEB_SEARCH_PROGRESS_MARKER = "[[WEB_SEARCH_PROGRESS]]"


def _encode_web_search_progress(content: str) -> str:
    return f"{WEB_SEARCH_PROGRESS_MARKER}{json.dumps(content, ensure_ascii=False)}\n"


class _NoopRAGService:
    def delete_video(self, *_args, **_kwargs):
        return None

    def delete_video_in_knowledge_base(self, *_args, **_kwargs):
        return None

    def add_video_content(self, *_args, **_kwargs):
        return 0


def _get_rag_service_for_build():
    try:
        return get_rag_service()
    except Exception as exc:
        logger.warning(
            f"知识库向量服务不可用，入库将仅写入数据库内容并跳过向量化: {exc}"
        )
        return _NoopRAGService()


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


async def _legacy_execute_web_search_tool(
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
) -> dict:
    return await _execute_web_search_tool_impl(
        arguments,
        web_results,
        state,
        search_web=getattr(_knowledge_web_search_module(), "search_web"),
    )


async def _legacy_execute_fetch_web_page_tool(
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
) -> dict:
    return await _execute_fetch_web_page_tool_impl(
        arguments,
        web_results,
        state,
        fetch_web_page=getattr(_knowledge_web_search_module(), "fetch_web_page"),
    )


async def _legacy_run_initial_web_search(
    question: str,
    web_results: list[dict[str, str]],
    state: dict,
) -> None:
    return await _run_initial_web_search_impl(
        question,
        web_results,
        state,
        search_web=getattr(_knowledge_web_search_module(), "search_web"),
    )


async def _legacy_prepare_web_search_tool_run(
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
):
    module = _knowledge_web_search_module()
    return await _prepare_web_search_tool_run_impl(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
        prepare_llm_messages_with_tools=getattr(
            module,
            "_prepare_llm_messages_with_tools",
        ),
        search_web=getattr(module, "search_web"),
        fetch_web_page=getattr(module, "fetch_web_page"),
    )


async def _complete_knowledge_base_answer(
    messages: list[dict],
    *,
    question: str,
    enable_web_search: bool,
    web_search_provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
) -> tuple[str, str, list[dict[str, str]], dict | None]:
    def complete_llm_with_config(next_messages: list[dict]) -> tuple[str, str]:
        kwargs = {}
        if _supports_keyword_argument(_complete_llm_answer, "llm_config"):
            kwargs["llm_config"] = llm_config
        return _complete_llm_answer(next_messages, **kwargs)

    if not enable_web_search:
        answer, thinking = complete_llm_with_config(messages)
        return answer, thinking, [], None

    tool_run, web_results, web_search_state = await getattr(
        _knowledge_web_search_module(),
        "_prepare_web_search_tool_run",
    )(
        messages,
        question=question,
        provider=web_search_provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
    )
    if tool_run.answer is not None:
        answer = tool_run.answer
        thinking = tool_run.thinking
    else:
        answer, thinking = complete_llm_with_config(tool_run.messages)

    return (
        answer,
        thinking,
        web_results,
        _status_from_web_search_state(
            web_results,
            web_search_state,
        ),
    )


async def _legacy_prepare_knowledge_base_web_search(
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
) -> tuple:
    tool_run, web_results, web_search_state = await getattr(
        _knowledge_web_search_module(),
        "_prepare_web_search_tool_run",
    )(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
    )

    return (
        tool_run,
        web_results,
        _status_from_web_search_state(
            web_results,
            web_search_state,
        ),
    )


def _legacy_prepare_knowledge_base_web_search_with_heartbeats(
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
):
    module = _knowledge_web_search_module()
    return _prepare_knowledge_base_web_search_with_heartbeats_impl(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
        prepare_knowledge_base_web_search=getattr(
            module,
            "_prepare_knowledge_base_web_search",
        ),
        heartbeat_interval_seconds=getattr(
            module,
            "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        ),
        tool_prep_timeout_seconds=getattr(
            module,
            "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS",
        ),
    )


_WEB_SEARCH_ORCHESTRATION_COMPAT = {
    "MAX_FETCH_WEB_PAGE_CALLS": _MAX_FETCH_WEB_PAGE_CALLS,
    "FETCH_WEB_PAGE_CONTEXT_CHARS": _FETCH_WEB_PAGE_CONTEXT_CHARS,
    "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS": _WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS,
    "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS": _WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS,
    "_execute_web_search_tool": _legacy_execute_web_search_tool,
    "_execute_fetch_web_page_tool": _legacy_execute_fetch_web_page_tool,
    "_run_initial_web_search": _legacy_run_initial_web_search,
    "_prepare_web_search_tool_run": _legacy_prepare_web_search_tool_run,
    "_prepare_knowledge_base_web_search": _legacy_prepare_knowledge_base_web_search,
    "_prepare_knowledge_base_web_search_with_heartbeats": (
        _legacy_prepare_knowledge_base_web_search_with_heartbeats
    ),
}


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
    if not enabled or provider == "html":
        return None
    credential = await resolve_optional_user_api_credentials(db, user, "tavily")
    return credential.api_key if credential else None


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
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.workspace_id == current_workspace.id)
        .order_by(KnowledgeBase.id.asc())
    )
    return [_response(item) for item in result.scalars().all()]


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    description = payload.description.strip() if payload.description else None
    if description == "":
        description = None

    knowledge_base = KnowledgeBase(
        workspace_id=current_workspace.id,
        name=name,
        description=description,
        created_by=current_user.id,
    )
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    return _response(knowledge_base)


@router.get("/{knowledge_base_id}/stats")
async def get_knowledge_base_stats(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """知识库统计信息（含文件夹入库状态）。"""
    # 查询该知识库下的收藏夹状态
    folder_rows = await db.execute(
        select(
            FavoriteFolder.id,
            FavoriteFolder.media_id,
            FavoriteFolder.last_sync_at,
            FavoriteFolder.media_count,
        )
        .where(FavoriteFolder.knowledge_base_id == knowledge_base.id)
        .where(FavoriteFolder.last_sync_at.isnot(None))
        .order_by(FavoriteFolder.updated_at.desc())
    )
    folders_data = []
    for row in folder_rows.all():
        fid, media_id, last_sync, media_count = row
        # 统计已入库视频数
        count_result = await db.execute(
            select(func.count(func.distinct(FavoriteVideo.bvid))).where(
                FavoriteVideo.folder_id == fid
            )
        )
        indexed = count_result.scalar() or 0
        folders_data.append(
            {
                "media_id": media_id,
                "indexed_count": indexed,
                "media_count": media_count,
                "last_sync_at": last_sync.isoformat() if last_sync else None,
            }
        )

    # 总视频数
    total_result = await db.execute(
        select(func.count(func.distinct(FavoriteVideo.bvid))).where(
            FavoriteVideo.knowledge_base_id == knowledge_base.id
        )
    )
    total_videos = total_result.scalar() or 0

    return {
        "knowledge_base_id": knowledge_base.id,
        "workspace_id": knowledge_base.workspace_id,
        "total_videos": total_videos,
        "folders": folders_data,
        "scoped": True,
    }


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
    binding = await db.get(SourceBinding, payload.source_binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="Source binding not found")

    folder_ids = _dedupe_ints(payload.folder_ids)
    video_folder_ids = _dedupe_ints(payload.video_folder_ids)
    include_bvids = set(_dedupe_strings(payload.bvids))

    if not folder_ids and not (video_folder_ids and include_bvids):
        raise HTTPException(status_code=400, detail="folder_ids cannot be empty")

    # 获取加密凭据
    cred_result = await db.execute(
        select(SourceCredential)
        .where(SourceCredential.source_binding_id == binding.id)
        .where(SourceCredential.revoked_at.is_(None))
        .order_by(SourceCredential.id.desc())
    )
    credential = cred_result.scalars().first()
    if credential is None:
        raise HTTPException(status_code=400, detail="内容源凭据不存在或已失效")

    try:
        cred_payload = json.loads(decrypt_text(credential.encrypted_payload))
    except Exception:
        raise HTTPException(status_code=500, detail="凭据解密失败")

    task_id = await create_ingestion_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
        user_id=current_user.id,
        current_step="初始化中...",
    )

    bili = bilibili_service_from_cookies(cred_payload, BilibiliService)
    asr_service = ASRService()
    content_fetcher = ContentFetcher(bili, asr_service)
    rag = _get_rag_service_for_build()
    exclude_bvids = set(payload.exclude_bvids) if payload.exclude_bvids else set()

    background_tasks.add_task(
        _run_scoped_build,
        task_id=task_id,
        bili=bili,
        rag=rag,
        content_fetcher=content_fetcher,
        folder_ids=folder_ids,
        video_folder_ids=video_folder_ids,
        include_bvids=include_bvids,
        exclude_bvids=exclude_bvids,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
    )

    return KnowledgeBaseBuildResponse(
        task_id=task_id,
        status="pending",
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
    )


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
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    bvids = await _resolve_request_scope(
        db,
        knowledge_base_id=knowledge_base.id,
        folder_ids=payload.folder_ids,
        bvids=payload.bvids,
    )
    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        query,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
        bvids=bvids,
    )
    return KnowledgeBaseSearchResponse(
        results=[_search_result(document) for document in documents]
    )


@router.post("/{knowledge_base_id}/chat", response_model=ChatResponse)
async def chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    question = payload.question.strip()
    documents = await _load_scoped_chat_documents(
        payload,
        knowledge_base,
        current_workspace,
        db,
        allow_db_fallback=not payload.web_search,
    )
    if not documents and not payload.web_search:
        response = _answer_from_documents(question, documents)
        return response

    credential = await resolve_user_llm_credentials(
        db,
        current_user,
        global_config_resolver=_resolve_llm_config,
    )
    llm_config = credential.to_llm_config()
    tavily_api_key = await _resolve_web_search_api_key(
        db,
        current_user,
        enabled=payload.web_search,
        provider=payload.web_search_provider,
    )

    messages = _build_knowledge_base_messages(
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
        if _supports_keyword_argument(
            _complete_knowledge_base_answer,
            "web_search_provider",
        ):
            complete_kwargs["web_search_provider"] = payload.web_search_provider
        if _supports_keyword_argument(
            _complete_knowledge_base_answer, "tavily_api_key"
        ):
            complete_kwargs["tavily_api_key"] = tavily_api_key
        if _supports_keyword_argument(_complete_knowledge_base_answer, "llm_config"):
            complete_kwargs["llm_config"] = llm_config
        answer, thinking, web_results, web_search_status = (
            await _complete_knowledge_base_answer(
                messages,
                **complete_kwargs,
            )
        )
    except Exception as exc:
        await record_usage_event(
            db,
            user=current_user,
            credential=credential,
            feature="chat",
            status="failed",
            error_code=exc.__class__.__name__,
        )
        await db.commit()
        logger.warning(f"知识库模型回答失败，回退到检索内容: {exc}")
        response = _answer_from_documents(question, documents)
        if payload.web_search:
            response.web_search = _web_search_failed_status_from_exception(exc)
        return response
    await record_usage_event(
        db,
        user=current_user,
        credential=credential,
        feature="chat",
        status="success",
    )
    await db.commit()
    return ChatResponse(
        answer=answer,
        thinking=thinking or None,
        sources=[
            *[_source_from_document(document) for document in documents],
            *[_source_from_web_result(result) for result in web_results],
        ],
        web_search=web_search_status,
    )


@router.post("/{knowledge_base_id}/chat/stream")
async def stream_chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    question = payload.question.strip()
    documents = await _load_scoped_chat_documents(
        payload,
        knowledge_base,
        current_workspace,
        db,
        allow_db_fallback=not payload.web_search,
    )
    credential = None
    llm_config = None
    if documents or payload.web_search:
        credential = await resolve_user_llm_credentials(
            db,
            current_user,
            global_config_resolver=_resolve_llm_config,
        )
        llm_config = credential.to_llm_config()
    tavily_api_key = await _resolve_web_search_api_key(
        db,
        current_user,
        enabled=payload.web_search,
        provider=payload.web_search_provider,
    )

    async def generate():
        if not documents and not payload.web_search:
            yield _answer_from_documents(question, documents).answer
            yield "\n[[SOURCES_JSON]][]"
            return

        messages = _build_knowledge_base_messages(
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
            yield _encode_web_search_progress("正在联网搜索外部资料")
            try:
                async for (
                    event_type,
                    event_payload,
                ) in getattr(
                    _knowledge_web_search_module(),
                    "_prepare_knowledge_base_web_search_with_heartbeats",
                )(
                    messages,
                    question=question,
                    provider=payload.web_search_provider,
                    tavily_api_key=tavily_api_key,
                    llm_config=llm_config,
                ):
                    if event_type == "heartbeat":
                        yield _encode_web_search_progress(str(event_payload))
                        continue
                    tool_run, web_results, web_search_status = event_payload
                prepared_messages = _append_no_more_tool_calls_instruction(
                    tool_run.messages
                )
            except Exception as exc:
                logger.warning(f"知识库联网工具链准备失败，将仅使用知识库回答: {exc!r}")
                web_search_status = _web_search_failed_status_from_exception(exc)
            finally:
                yield _encode_web_search_progress("")
        sources = [
            *[_source_from_document(document) for document in documents],
            *[_source_from_web_result(result) for result in web_results],
        ]
        answer_started = False
        try:
            stream_kwargs = {}
            if _supports_keyword_argument(_stream_llm_events, "llm_config"):
                stream_kwargs["llm_config"] = llm_config
            for event_type, content in _stream_llm_events(
                prepared_messages,
                **stream_kwargs,
            ):
                if event_type == "thinking":
                    thinking_parts.append(content)
                    yield _encode_thinking_delta(content)
                else:
                    answer_started = True
                    yield content
        except Exception as exc:
            logger.warning(f"知识库流式模型回答失败，回退到检索内容: {exc}")
            if not answer_started:
                yield _answer_from_documents(question, documents).answer
        if thinking_parts:
            yield "\n[[THINKING_JSON]]"
            yield json.dumps("".join(thinking_parts), ensure_ascii=False)
        if web_search_status:
            yield "\n[[WEB_SEARCH_JSON]]"
            yield json.dumps(web_search_status, ensure_ascii=False)
        yield "\n[[SOURCES_JSON]]"
        yield json.dumps(sources, ensure_ascii=False)
        if credential is not None:
            await record_usage_event(
                db,
                user=current_user,
                credential=credential,
                feature="chat",
                status="success",
            )
            await db.commit()

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除知识库及其相关数据。"""
    kb_id = knowledge_base.id

    deleted_vectors = 0
    try:
        rag = get_rag_service()
        if _supports_keyword_argument(rag.delete_by_knowledge_base, "workspace_id"):
            deleted_vectors = rag.delete_by_knowledge_base(
                kb_id,
                workspace_id=current_workspace.id,
            )
        else:
            deleted_vectors = rag.delete_by_knowledge_base(kb_id)
        logger.info(
            f"已删除知识库 {kb_id}（{knowledge_base.name}）的 {deleted_vectors} 个向量"
        )
    except Exception as exc:
        logger.warning(f"删除知识库向量失败 [{kb_id}]: {exc}")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "vector_cleanup_failed",
                "message": f"向量清理失败，知识库未删除，请稍后重试或检查向量服务：{exc}",
            },
        ) from exc

    await db.execute(
        IngestionTask.__table__.delete().where(IngestionTask.knowledge_base_id == kb_id)
    )
    await db.execute(
        FavoriteFolder.__table__.delete().where(
            FavoriteFolder.knowledge_base_id == kb_id
        )
    )
    await db.execute(
        FavoriteVideo.__table__.delete().where(FavoriteVideo.knowledge_base_id == kb_id)
    )
    await db.execute(
        VideoCache.__table__.delete().where(VideoCache.knowledge_base_id == kb_id)
    )
    await db.execute(
        VideoTitleOverride.__table__.delete().where(
            VideoTitleOverride.knowledge_base_id == kb_id
        )
    )
    await db.delete(knowledge_base)
    await db.commit()

    result: dict[str, object] = {"ok": True, "deleted_vectors": deleted_vectors}
    return result
