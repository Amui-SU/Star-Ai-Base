"""Favorite-folder ingestion service shared by legacy and scoped routes."""

from typing import Callable, Optional

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteVideo
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.folder_ingestion_content import (
    is_better_source as _is_better_source,
    should_refresh_cache as _should_refresh_cache,
    video_content_from_cache as _video_content_from_cache,
)
from app.services.folder_ingestion_plan import (
    build_video_map as _build_video_map,
    diff_folder_videos as _diff_folder_videos,
)
from app.services.folder_ingestion_records import (
    delete_video_vectors_for_scope as _delete_video_vectors_for_scope,
    get_existing_folder_for_scope as _get_existing_folder_for_scope,
    get_or_create_folder as _get_or_create_folder,
    get_video_cache_for_scope as _get_video_cache_for_scope,
    has_cache_scope as _has_cache_scope,
    upsert_video_cache as _upsert_video_cache,
)
from app.services.folder_ingestion_vector_runtime import (
    has_scoped_vectors as _has_scoped_vectors,
    process_vector_target as _process_vector_target,
)
from app.services.rag import RAGService
from app.time_utils import utc_now


async def sync_folder(
    db: AsyncSession,
    bili: BilibiliService,
    rag: RAGService,
    content_fetcher: ContentFetcher,
    session_id: str,
    folder_id: int,
    exclude_bvids: Optional[set[str]] = None,
    include_bvids: Optional[set[str]] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> dict:
    """同步单个收藏夹到向量库。可选 scoped 参数用于多用户范围写入。"""
    info = {}
    try:
        info_result = await bili.get_favorite_content(folder_id, pn=1, ps=1)
        info = info_result.get("info", {})
    except Exception as e:
        logger.warning(f"获取收藏夹信息失败 [{folder_id}]: {e}")

    videos = await bili.get_all_favorite_videos(folder_id)
    total_in_folder = info.get("media_count", len(videos))

    # 保护：接口异常返回空列表时，避免误删
    if not videos:
        if total_in_folder and total_in_folder > 0:
            logger.warning(f"[{folder_id}] 收藏夹返回空列表，跳过删除逻辑")
            existing_folder = await _get_existing_folder_for_scope(
                db,
                session_id=session_id,
                media_id=folder_id,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=source_binding_id,
            )
            existing_count = 0
            if existing_folder is not None:
                existing_count = await db.scalar(
                    select(func.count(FavoriteVideo.bvid)).where(
                        FavoriteVideo.folder_id == existing_folder.id
                    )
                )
            return {
                "folder_id": folder_id,
                "total": total_in_folder,
                "added": 0,
                "removed": 0,
                "indexed": existing_count or 0,
                "message": "本次同步异常：空列表，已跳过",
                "last_sync_at": utc_now(),
            }

    video_map, skipped_invalid = _build_video_map(
        videos,
        include_bvids=include_bvids,
        exclude_bvids=exclude_bvids,
    )

    if skipped_invalid > 0:
        logger.info(f"[{folder_id}] 过滤了 {skipped_invalid} 个失效视频")

    # 以有效视频数作为统计口径（过滤失效视频）
    valid_count = len(video_map)
    current_bvids = set(video_map.keys())

    folder = await _get_or_create_folder(
        db,
        session_id=session_id,
        media_id=folder_id,
        title=info.get("title"),
        media_count=valid_count,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )

    # 多用户范围：写入归属字段
    if workspace_id is not None:
        folder.workspace_id = workspace_id
    if knowledge_base_id is not None:
        folder.knowledge_base_id = knowledge_base_id
    if source_binding_id is not None:
        folder.source_binding_id = source_binding_id

    existing_rows = await db.execute(
        select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder.id)
    )
    existing_bvids = {row[0] for row in existing_rows.fetchall()}

    added, removed = _diff_folder_videos(
        current_bvids=current_bvids,
        existing_bvids=existing_bvids,
        partial=include_bvids is not None,
    )

    # 写入标题/简介等信息（含多用户范围）
    for bvid, meta in video_map.items():
        await _upsert_video_cache(
            db,
            bvid,
            meta,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
        )

    # 需要更新的已存在视频（缓存过少或来源较弱）
    update_candidates: set[str] = set()
    for bvid in current_bvids & existing_bvids:
        if bvid in added:
            continue
        cache = await _get_video_cache_for_scope(
            db,
            bvid,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
        )
        if _should_refresh_cache(cache):
            update_candidates.add(bvid)

    # 新增/更新向量与关联
    missing_vector_candidates: set[str] = set()
    if _has_cache_scope(workspace_id, knowledge_base_id):
        for bvid in current_bvids:
            if not _has_scoped_vectors(
                rag,
                bvid,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                warn=logger.warning,
            ):
                missing_vector_candidates.add(bvid)

    targets = list(added | update_candidates | missing_vector_candidates)
    total_targets = len(targets)
    processed_targets = 0
    if progress_callback:
        progress_callback("准备处理", processed_targets, total_targets)
    for bvid in targets:
        meta = video_map[bvid]

        # 尝试添加到向量库（可能失败，但不影响记录入库）
        try:
            await _process_vector_target(
                db=db,
                bvid=bvid,
                meta=meta,
                rag=rag,
                content_fetcher=content_fetcher,
                missing_vector_candidates=missing_vector_candidates,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=source_binding_id,
                warn=logger.warning,
                info=logger.info,
                load_cache=_get_video_cache_for_scope,
                refresh_checker=_should_refresh_cache,
                source_ranker=_is_better_source,
                cache_to_content=_video_content_from_cache,
                delete_vectors=_delete_video_vectors_for_scope,
            )
        except Exception as e:
            logger.warning(f"添加向量失败 [{bvid}]: {e} (仍会记录到数据库)")

        # 无论向量是否添加成功，都写入 FavoriteVideo 记录
        try:
            exists_row = await db.execute(
                select(FavoriteVideo.id).where(
                    FavoriteVideo.folder_id == folder.id,
                    FavoriteVideo.bvid == bvid,
                )
            )
            if exists_row.scalar_one_or_none() is None:
                fav_kwargs: dict = {
                    "folder_id": folder.id,
                    "bvid": bvid,
                    "is_selected": True,
                }
                if workspace_id is not None:
                    fav_kwargs["workspace_id"] = workspace_id
                if knowledge_base_id is not None:
                    fav_kwargs["knowledge_base_id"] = knowledge_base_id
                if source_binding_id is not None:
                    fav_kwargs["source_binding_id"] = source_binding_id
                db.add(FavoriteVideo(**fav_kwargs))
            processed_targets += 1
            if progress_callback:
                progress_callback(meta["title"], processed_targets, total_targets)
        except Exception as e:
            logger.error(f"写入数据库失败 [{bvid}]: {e}")

    # 删除无效向量
    if removed:
        for bvid in removed:
            other_count_stmt = (
                select(func.count())
                .select_from(FavoriteVideo)
                .where(
                    FavoriteVideo.bvid == bvid,
                    FavoriteVideo.folder_id != folder.id,
                )
            )
            if _has_cache_scope(workspace_id, knowledge_base_id):
                other_count_stmt = (
                    other_count_stmt.where(FavoriteVideo.workspace_id == workspace_id)
                    .where(FavoriteVideo.knowledge_base_id == knowledge_base_id)
                    .where(
                        FavoriteVideo.source_binding_id.is_(None)
                        if source_binding_id is None
                        else FavoriteVideo.source_binding_id == source_binding_id
                    )
                )
            else:
                other_count_stmt = other_count_stmt.where(
                    FavoriteVideo.workspace_id.is_(None)
                ).where(FavoriteVideo.knowledge_base_id.is_(None))
            other_count = await db.scalar(other_count_stmt)
            if other_count == 0:
                try:
                    _delete_video_vectors_for_scope(
                        rag,
                        bvid,
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base_id,
                    )
                except Exception as e:
                    logger.warning(f"删除向量失败 [{bvid}]: {e}")

        await db.execute(
            delete(FavoriteVideo).where(
                FavoriteVideo.folder_id == folder.id,
                FavoriteVideo.bvid.in_(removed),
            )
        )

    folder.last_sync_at = utc_now()

    await db.commit()

    indexed_count = await db.scalar(
        select(func.count(func.distinct(FavoriteVideo.bvid)))
        .select_from(FavoriteVideo)
        .where(FavoriteVideo.folder_id == folder.id)
    )

    return {
        "folder_id": folder_id,
        "total": valid_count,
        "added": len(added),
        "removed": len(removed),
        "indexed": indexed_count or 0,
        "message": "同步完成",
        "last_sync_at": folder.last_sync_at,
    }
