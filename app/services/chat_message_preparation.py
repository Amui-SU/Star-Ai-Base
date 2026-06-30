"""Message preparation orchestration for legacy chat routes."""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatRequest
from app.services.chat_messages import (
    build_db_list_messages,
    build_db_summary_messages,
    build_direct_messages,
    build_direct_messages_with_context,
    build_fallback_messages,
    build_rag_messages,
)
from app.services.chat_routing import (
    filter_docs_by_keywords,
    is_collection_intent,
    is_general_question,
    route_with_llm,
    route_with_rules,
)
from app.services.chat_video_context import (
    get_bvids_by_folder_ids,
    get_folder_ids_for_session,
    get_video_context,
    get_video_titles_context,
    is_related_to_collection,
)
from app.services.rag_runtime import get_rag_service

FolderIdsLoader = Callable[[AsyncSession, str, list[int] | None], Awaitable[list[int]]]
BvidsLoader = Callable[[AsyncSession, list[int]], Awaitable[list[str]]]
RelatedChecker = Callable[[AsyncSession, list[int], str], Awaitable[bool]]
VideoContextLoader = Callable[..., Awaitable[tuple[str, list[dict]]]]
VideoTitlesLoader = Callable[..., Awaitable[str]]
MessagesBuilder = Callable[..., list[dict]]
RAGFactory = Callable[[], Any]


async def prepare_chat_messages(
    request: ChatRequest,
    db: AsyncSession,
    *,
    get_folder_ids: FolderIdsLoader = get_folder_ids_for_session,
    get_bvids: BvidsLoader = get_bvids_by_folder_ids,
    check_related: RelatedChecker = is_related_to_collection,
    load_video_context: VideoContextLoader = get_video_context,
    load_video_titles_context: VideoTitlesLoader = get_video_titles_context,
    get_rag: RAGFactory = get_rag_service,
    collection_intent_detector: Callable[[str], bool] = is_collection_intent,
    general_question_detector: Callable[[str], bool] = is_general_question,
    llm_router: Callable[..., tuple[str | None, str]] = route_with_llm,
    rules_router: Callable[[str, bool, bool], str] = route_with_rules,
    doc_filter: Callable[[list, str], list] = filter_docs_by_keywords,
    build_fallback: MessagesBuilder = build_fallback_messages,
    build_direct: MessagesBuilder = build_direct_messages,
    build_direct_with_context: MessagesBuilder = build_direct_messages_with_context,
    build_db_list: MessagesBuilder = build_db_list_messages,
    build_db_summary: MessagesBuilder = build_db_summary_messages,
    build_rag: MessagesBuilder = build_rag_messages,
    resolve_llm_config: Callable[[], dict[str, Any]],
    get_llm_client: Callable[[dict[str, Any]], Any],
    log_info: Callable[[str], None],
    log_warning: Callable[[str], None],
) -> tuple[list[dict], list[dict], str]:
    """Prepare LLM messages and source metadata for legacy chat."""
    question = request.question.strip()
    rag = get_rag()
    folder_ids = []
    if request.session_id:
        folder_ids = await get_folder_ids(db, request.session_id, request.folder_ids)
        log_info(f"Session: {request.session_id}, \u5173\u8054 FolderIDs: {folder_ids}")

    bvids = await get_bvids(db, folder_ids) if folder_ids else []
    has_data = len(bvids) > 0
    is_collection_intent_value = collection_intent_detector(question)
    is_general = general_question_detector(question)
    if request.folder_ids:
        is_collection_intent_value = True

    log_info(
        "\u8def\u7531\u8f93\u5165: "
        f"question={question} "
        f"folder_ids={folder_ids} "
        f"has_data={has_data} "
        f"is_collection_intent={is_collection_intent_value}"
    )
    route, _route_raw = llm_router(
        question,
        resolve_llm_config=resolve_llm_config,
        get_llm_client=get_llm_client,
        log_warning=log_warning,
    )
    route_source = "LLM"
    related: bool | None = None
    if not route:
        related = await check_related(db, folder_ids, question)
        route = rules_router(question, is_collection_intent_value, related)
        route_source = "RULE"
    log_info(f"\u8def\u7531\u7b56\u7565: {route_source} => {route}")

    if is_general:
        route = "direct"

    if not has_data:
        if is_collection_intent_value:
            context, sources = await load_video_context(
                db, folder_ids, include_content=False, limit=50
            )
            if not context:
                context = "\uff08\u6682\u65e0\u5df2\u5165\u5e93\u7684\u89c6\u9891\u4fe1\u606f\uff0c\u8bf7\u63d0\u9192\u7528\u6237\u53ef\u80fd\u9700\u8981\u5148\u8fdb\u884c\u5165\u5e93\u64cd\u4f5c\uff09"
            messages = build_fallback(context, question)
            return messages, sources, question
        messages = build_direct(question)
        return messages, [], question

    if route == "direct":
        title_context = await load_video_titles_context(db, folder_ids, limit=50)
        messages = (
            build_direct_with_context(title_context, question)
            if title_context
            else build_direct(question)
        )
        return messages, [], question

    if route == "db_list":
        if related is None:
            related = await check_related(db, folder_ids, question)
        if not related and not is_collection_intent_value:
            return build_direct(question), [], question
        context, sources = await load_video_context(
            db, folder_ids, include_content=False, limit=50
        )
        if not context:
            return (
                build_fallback(
                    "\uff08\u6682\u65e0\u4fe1\u606f\uff0c\u8bf7\u5165\u5e93\uff09",
                    question,
                ),
                sources,
                question,
            )
        return build_db_list(context, question), sources, question

    if route == "db_content":
        if related is None:
            related = await check_related(db, folder_ids, question)
        if not related and not is_collection_intent_value:
            return build_direct(question), [], question
        context, sources = await load_video_context(
            db, folder_ids, include_content=True, limit=None
        )
        if not context:
            return (
                build_fallback(
                    "\uff08\u6682\u65e0\u4fe1\u606f\uff0c\u8bf7\u5165\u5e93\uff09",
                    question,
                ),
                sources,
                question,
            )
        return build_db_summary(context, question), sources, question

    if related is None:
        related = await check_related(db, folder_ids, question)
    if not related and not is_collection_intent_value:
        return build_direct(question), [], question

    docs = []
    try:
        docs = rag.search(question, k=5, bvids=bvids if bvids else None)
    except Exception as exc:
        log_warning(f"\u5411\u91cf\u68c0\u7d22\u5931\u8d25: {exc}")
    if docs:
        filtered_docs = doc_filter(docs, question)
        docs = filtered_docs if filtered_docs else docs
        context_parts, sources, seen_bvids = [], [], set()
        for doc in docs:
            bvid, title, content = (
                doc.metadata.get("bvid", ""),
                doc.metadata.get("title", ""),
                doc.page_content.strip(),
            )
            if content:
                context_parts.append(f"\u3010{title}\u3011\n{content}")
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
            build_rag("\n\n---\n\n".join(context_parts), question),
            sources,
            question,
        )

    context, sources = await load_video_context(
        db, folder_ids, include_content=False, limit=50
    )
    return (
        build_fallback(
            context or "\uff08\u6682\u65e0\u5165\u5e93\u4fe1\u606f\uff09",
            question,
        ),
        sources,
        question,
    )
