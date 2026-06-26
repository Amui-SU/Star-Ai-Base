"""Favorite-folder ingestion service shared by legacy and scoped routes."""

from datetime import datetime, timezone
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ContentSource,
    FavoriteFolder,
    FavoriteVideo,
    VideoCache,
    VideoContent,
)
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.rag import RAGService


async def _get_or_create_folder(
    db: AsyncSession,
    session_id: str,
    media_id: int,
    title: Optional[str] = None,
    media_count: Optional[int] = None,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> FavoriteFolder:
    """获取或创建收藏夹记录"""
    stmt = select(FavoriteFolder).where(
        FavoriteFolder.session_id == session_id,
        FavoriteFolder.media_id == media_id,
    )
    if _has_cache_scope(workspace_id, knowledge_base_id):
        stmt = (
            stmt.where(FavoriteFolder.workspace_id == workspace_id)
            .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
            .where(
                FavoriteFolder.source_binding_id.is_(None)
                if source_binding_id is None
                else FavoriteFolder.source_binding_id == source_binding_id
            )
        )
    else:
        stmt = stmt.where(FavoriteFolder.workspace_id.is_(None)).where(
            FavoriteFolder.knowledge_base_id.is_(None)
        )
    result = await db.execute(stmt.order_by(FavoriteFolder.id.asc()).limit(1))
    folder = result.scalar_one_or_none()

    if folder is None:
        folder = FavoriteFolder(
            session_id=session_id,
            media_id=media_id,
            title=title or "",
            media_count=media_count or 0,
            is_selected=True,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
        )
        db.add(folder)
        await db.flush()
    else:
        if title:
            folder.title = title
        if media_count is not None:
            folder.media_count = media_count

    return folder


def _extract_video_info(media: dict) -> tuple[str, str, Optional[int]]:
    """抽取视频关键信息"""
    bvid = media.get("bvid") or media.get("bv_id")
    title = media.get("title", bvid)
    cid = None
    ugc = media.get("ugc") or {}
    if ugc.get("first_cid"):
        cid = ugc.get("first_cid")
    else:
        cid = media.get("cid") or media.get("id")
    return bvid, title, cid


def _has_cache_scope(
    workspace_id: Optional[int],
    knowledge_base_id: Optional[int],
) -> bool:
    return workspace_id is not None and knowledge_base_id is not None


async def _get_video_cache_for_scope(
    db: AsyncSession,
    bvid: str,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> Optional[VideoCache]:
    stmt = select(VideoCache).where(VideoCache.bvid == bvid)
    if _has_cache_scope(workspace_id, knowledge_base_id):
        stmt = (
            stmt.where(VideoCache.workspace_id == workspace_id)
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(
                VideoCache.source_binding_id.is_(None)
                if source_binding_id is None
                else VideoCache.source_binding_id == source_binding_id
            )
        )
    else:
        stmt = stmt.where(VideoCache.workspace_id.is_(None)).where(
            VideoCache.knowledge_base_id.is_(None)
        )
    stmt = stmt.order_by(VideoCache.id.asc()).limit(1)
    result = await db.execute(stmt)
    return result.scalars().first()


def _delete_video_vectors_for_scope(
    rag: RAGService,
    bvid: str,
    *,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
) -> None:
    if _has_cache_scope(workspace_id, knowledge_base_id):
        rag.delete_video_in_knowledge_base(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
        return
    rag.delete_video(bvid)


async def _upsert_video_cache(
    db: AsyncSession,
    bvid: str,
    meta: dict,
    workspace_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    source_binding_id: Optional[int] = None,
) -> None:
    """写入或更新视频缓存信息"""
    cache = await _get_video_cache_for_scope(
        db,
        bvid,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=source_binding_id,
    )

    scoped_fields = {}
    if workspace_id is not None:
        scoped_fields["workspace_id"] = workspace_id
    if knowledge_base_id is not None:
        scoped_fields["knowledge_base_id"] = knowledge_base_id
    if source_binding_id is not None:
        scoped_fields["source_binding_id"] = source_binding_id

    if cache is None:
        cache = VideoCache(
            bvid=bvid,
            title=meta.get("title") or bvid,
            description=meta.get("intro"),
            owner_name=meta.get("owner_name"),
            owner_mid=meta.get("owner_mid"),
            duration=meta.get("duration"),
            pic_url=meta.get("cover"),
            is_processed=False,
            **scoped_fields,
        )
        db.add(cache)
        return

    cache.title = meta.get("title") or cache.title
    if meta.get("intro") is not None:
        cache.description = meta.get("intro")
    if meta.get("owner_name") is not None:
        cache.owner_name = meta.get("owner_name")
    if meta.get("owner_mid") is not None:
        cache.owner_mid = meta.get("owner_mid")
    if meta.get("duration") is not None:
        cache.duration = meta.get("duration")
    if meta.get("cover") is not None:
        cache.pic_url = meta.get("cover")
    for key, val in scoped_fields.items():
        setattr(cache, key, val)


async def sync_folder(
    db: AsyncSession,
    bili: BilibiliService,
    rag: RAGService,
    content_fetcher: ContentFetcher,
    session_id: str,
    folder_id: int,
    exclude_bvids: Optional[set[str]] = None,
    include_bvids: Optional[set[str]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
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
            existing_count = await db.scalar(
                select(func.count(FavoriteVideo.bvid)).where(
                    FavoriteVideo.folder_id == folder_id
                )
            )
            return {
                "folder_id": folder_id,
                "total": total_in_folder,
                "added": 0,
                "removed": 0,
                "indexed": existing_count or 0,
                "message": "本次同步异常：空列表，已跳过",
                "last_sync_at": datetime.now(timezone.utc),
            }

    video_map = {}
    skipped_invalid = 0
    for media in videos:
        bvid, title, cid = _extract_video_info(media)
        if not bvid:
            continue
        if include_bvids is not None and bvid not in include_bvids:
            continue
        if exclude_bvids and bvid in exclude_bvids:
            continue

        # 过滤失效视频（被删除、下架等）
        # attr 字段: 0=正常, 9=已失效, 1=私密等
        attr = media.get("attr", 0)
        if attr == 9 or title in ["已失效视频", "已删除视频"]:
            skipped_invalid += 1
            logger.debug(f"跳过失效视频: {bvid} - {title}")
            continue

        owner = media.get("upper") or {}
        video_map[bvid] = {
            "title": title,
            "cid": cid,
            "intro": media.get("intro"),
            "cover": media.get("cover"),
            "duration": media.get("duration"),
            "owner_name": owner.get("name"),
            "owner_mid": owner.get("mid"),
        }

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

    added = current_bvids - existing_bvids
    removed = set() if include_bvids is not None else existing_bvids - current_bvids

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

    source_priority = {
        ContentSource.BASIC_INFO.value: 1,
        ContentSource.AI_SUMMARY.value: 2,
        ContentSource.SUBTITLE.value: 3,
        ContentSource.ASR.value: 4,
    }

    def _is_better_source(new_source: str, old_source: Optional[str]) -> bool:
        return source_priority.get(new_source, 0) > source_priority.get(
            old_source or "", 0
        )

    def _should_refresh_cache(cache: Optional[VideoCache]) -> bool:
        if not cache:
            return True
        text = (cache.content or "").strip()
        if len(text) < 50:
            return True
        if cache.content_source in (None, "", ContentSource.BASIC_INFO.value):
            return True
        return False

    def _is_asr_cache_usable(cache: Optional[VideoCache]) -> bool:
        if not cache:
            return False
        if cache.content_source != ContentSource.ASR.value:
            return False
        text = (cache.content or "").strip()
        return len(text) >= 50

    def _video_content_from_cache(
        cache: Optional[VideoCache], bvid: str, title: str
    ) -> Optional[VideoContent]:
        if not cache:
            return None
        text = (cache.content or "").strip()
        if len(text) < 10:
            return None
        try:
            source = ContentSource(cache.content_source)
        except Exception:
            source = ContentSource.BASIC_INFO
        return VideoContent(
            bvid=bvid,
            title=title,
            content=text,
            source=source,
            outline=cache.outline_json,
        )

    def _has_scoped_vectors(bvid: str) -> bool:
        if not _has_cache_scope(workspace_id, knowledge_base_id):
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
            logger.warning(f"检查 scoped 向量失败 [{knowledge_base_id}/{bvid}]: {e}")
            return False

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
            if not _has_scoped_vectors(bvid):
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
            # 检查缓存内容是否缺失
            cache = await _get_video_cache_for_scope(
                db,
                bvid,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=source_binding_id,
            )
            old_content = (cache.content or "").strip() if cache else ""
            old_source = cache.content_source if cache else None

            needs_fetch = _should_refresh_cache(cache)
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
                elif new_source and _is_better_source(new_source, old_source):
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
                    logger.info(f"[{bvid}] 已写入缓存: source={cache.content_source}")

            # 需要重建向量：新增/升级/内容变化 或 向量缺失
            if bvid in missing_vector_candidates or should_reindex:
                if not content:
                    cached_content = _video_content_from_cache(
                        cache, bvid, meta["title"]
                    )
                    if cached_content:
                        content = cached_content
                        cache.is_processed = True
                        logger.info(f"[{bvid}] 使用缓存内容重建 scoped 向量")
                    elif _is_asr_cache_usable(cache):
                        content = VideoContent(
                            bvid=bvid,
                            title=meta["title"],
                            content=(cache.content or "").strip(),
                            source=ContentSource.ASR,
                            outline=cache.outline_json,
                        )
                        cache.is_processed = True
                        logger.info(f"[{bvid}] 使用缓存 ASR 内容重建向量")
                    else:
                        content = await content_fetcher.fetch_content(
                            bvid, cid=meta["cid"], title=meta["title"]
                        )
                        if cache:
                            cache.content = content.content
                            cache.content_source = content.source.value
                            cache.outline_json = content.outline
                            cache.is_processed = True
                            logger.info(
                                f"[{bvid}] 已写入缓存: source={cache.content_source}"
                            )
                try:
                    _delete_video_vectors_for_scope(
                        rag,
                        bvid,
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base_id,
                    )
                except Exception as e:
                    logger.warning(f"删除旧向量失败 [{bvid}]: {e}")
                chunks = rag.add_video_content(
                    content,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=source_binding_id,
                )
                logger.info(f"[{bvid}] 向量化完成，块数={chunks}")
            else:
                logger.info(f"[{bvid}] 内容未变化或无需升级，跳过向量化")
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

    folder.last_sync_at = datetime.now(timezone.utc)

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
