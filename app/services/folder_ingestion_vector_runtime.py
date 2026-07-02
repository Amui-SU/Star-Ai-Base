"""Vector rebuild helpers for favorite-folder ingestion."""

from collections.abc import Awaitable, Callable
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoCache
from app.services.content_fetcher import ContentFetcher
from app.services.folder_ingestion_content import (
    is_better_source,
    should_refresh_cache,
    video_content_from_cache,
)
from app.services.folder_ingestion_records import (
    delete_video_vectors_for_scope,
    get_video_cache_for_scope,
    has_cache_scope,
)
from app.services.rag import RAGService


def _noop_log(_message: str) -> None:
    return None


def has_scoped_vectors(
    rag: RAGService,
    bvid: str,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    warn: Callable[[str], None] = _noop_log,
) -> bool:
    if not has_cache_scope(workspace_id, knowledge_base_id):
        return True
    checker = getattr(rag, "has_video_vectors_in_knowledge_base", None)
    if checker is None:
        return False
    try:
        return bool(
            checker(
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                bvid=bvid,
            )
        )
    except Exception as e:
        warn(f"检查 scoped 向量失败 [{knowledge_base_id}/{bvid}]: {e}")
        return False


async def process_vector_target(
    *,
    db: AsyncSession,
    bvid: str,
    meta: dict,
    rag: RAGService,
    content_fetcher: ContentFetcher,
    missing_vector_candidates: set[str],
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
    warn: Callable[[str], None] = _noop_log,
    info: Callable[[str], None] = _noop_log,
    load_cache: Callable[
        ..., Awaitable[Optional[VideoCache]]
    ] = get_video_cache_for_scope,
    refresh_checker: Callable[[Optional[VideoCache]], bool] = should_refresh_cache,
    source_ranker: Callable[[str, Optional[str]], bool] = is_better_source,
    cache_to_content: Callable[..., object] = video_content_from_cache,
    delete_vectors: Callable[..., None] = delete_video_vectors_for_scope,
) -> None:
    cache = await load_cache(
        db,
        bvid,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )
    old_content = (cache.content or "").strip() if cache else ""
    old_source = cache.content_source if cache else None

    needs_fetch = refresh_checker(cache)
    content = None
    should_update_cache = False
    should_reindex = False

    if needs_fetch:
        content = await content_fetcher.fetch_content(
            bvid, cid=meta["cid"], title=meta["title"]
        )
        new_text = (content.content or "").strip() if content else ""
        new_source = content.source.value if content else None

        if not old_content:
            should_update_cache = True
            should_reindex = True
        elif new_source and source_ranker(new_source, old_source):
            should_update_cache = True
            should_reindex = True
        elif new_text and new_text != old_content:
            should_update_cache = True
            should_reindex = True

        if cache and should_update_cache:
            cache.content = content.content
            cache.content_source = content.source.value
            cache.outline_json = content.outline
            cache.is_processed = True
            info(f"[{bvid}] 已写入缓存: source={cache.content_source}")

    if bvid in missing_vector_candidates or should_reindex:
        if not content:
            cached_content = cache_to_content(cache, bvid, meta["title"])
            if cached_content:
                content = cached_content
                cache.is_processed = True
                info(f"[{bvid}] 使用缓存内容重建 scoped 向量")
            else:
                content = await content_fetcher.fetch_content(
                    bvid, cid=meta["cid"], title=meta["title"]
                )
                if cache:
                    cache.content = content.content
                    cache.content_source = content.source.value
                    cache.outline_json = content.outline
                    cache.is_processed = True
                    info(
                        f"[{bvid}] wrote refreshed cache source={cache.content_source}"
                    )
        try:
            delete_vectors(
                rag,
                bvid,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
            )
        except Exception as e:
            warn(f"删除旧向量失败 [{bvid}]: {e}")
        else:
            chunks = rag.add_video_content(
                content,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=source_binding_id,
            )
            info(f"[{bvid}] 向量化完成，块数={chunks}")
    else:
        info(f"[{bvid}] 内容未变化或无需升级，跳过向量化")
