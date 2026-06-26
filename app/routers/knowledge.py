"""
Bilibili RAG 知识库系统

知识库路由 - 构建和管理知识库
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from loguru import logger
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_db_context
from app.config import settings
from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    UserSession,
)
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.content_fetcher import ContentFetcher
from app.services.asr import ASRService
from app.services.folder_ingestion import sync_folder as _sync_folder
from app.services.rag_runtime import get_rag_service
from app.routers.auth import get_session

router = APIRouter(prefix="/knowledge", tags=["知识库"])
LEGACY_SCOPED_API_DETAIL = "旧全局接口已禁用，请使用 /knowledge-bases/* 范围化 API。"


def _raise_legacy_scoped_api_required() -> None:
    raise HTTPException(status_code=410, detail=LEGACY_SCOPED_API_DETAIL)


# 构建任务状态
build_tasks = {}


def get_collection_stats_without_embeddings(
    collection_name: str = "bilibili_videos",
) -> dict:
    """读取 Chroma 统计信息，不初始化 embedding/LLM 客户端。"""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_persist_directory)
        collection = client.get_collection(collection_name)
        count = collection.count()
        result = collection.get(include=["metadatas"])
        bvids = {
            meta["bvid"]
            for meta in result.get("metadatas", [])
            if meta and meta.get("bvid")
        }
        return {
            "total_chunks": count,
            "total_videos": len(bvids),
            "collection_name": collection_name,
        }
    except Exception as e:
        logger.warning(f"读取知识库统计信息失败，返回空统计: {e}")
        return {
            "total_chunks": 0,
            "total_videos": 0,
            "collection_name": collection_name,
        }


class BuildRequest(BaseModel):
    """知识库构建请求"""

    folder_ids: List[int]  # 要处理的收藏夹 ID 列表
    exclude_bvids: Optional[List[str]] = None  # 排除的视频


class BuildStatus(BaseModel):
    """构建状态"""

    task_id: str
    status: str  # pending / running / completed / failed
    progress: int  # 0-100
    current_step: str
    total_videos: int
    processed_videos: int
    message: str


class FolderStatus(BaseModel):
    """收藏夹入库状态"""

    media_id: int
    indexed_count: int
    media_count: Optional[int] = None
    last_sync_at: Optional[datetime] = None


class SyncRequest(BaseModel):
    """同步请求"""

    folder_ids: Optional[List[int]] = None


class SyncResult(BaseModel):
    """同步结果"""

    folder_id: int
    total: int
    added: int
    removed: int
    indexed: int
    message: str
    last_sync_at: Optional[datetime] = None


@router.get("/stats")
async def get_knowledge_stats():
    """获取知识库统计信息"""
    _raise_legacy_scoped_api_required()
    return get_collection_stats_without_embeddings()


@router.get("/folders/status", response_model=List[FolderStatus])
async def get_folder_status(
    session_id: Optional[str] = Query(None, description="会话ID"),
    db: AsyncSession = Depends(get_db),
):
    """获取收藏夹入库状态（跨 Session 查找同一用户的数据）"""
    _raise_legacy_scoped_api_required()

    # 1. 先查当前 Session 对应的用户 MID
    result = await db.execute(
        select(UserSession.bili_mid).where(UserSession.session_id == session_id)
    )
    mid = result.scalar()

    target_session_ids = [session_id]

    if mid:
        # 2. 如果有 MID，查找该用户所有的 Session ID
        result = await db.execute(
            select(UserSession.session_id).where(UserSession.bili_mid == mid)
        )
        target_session_ids = [row[0] for row in result.fetchall()]

    # 3. 查询所有关联 Session 的收藏夹状态
    # 使用 group_by media_id 来去重，取最新的那个
    rows = await db.execute(
        select(FavoriteFolder.id, FavoriteFolder.media_id, FavoriteFolder.last_sync_at)
        .where(FavoriteFolder.session_id.in_(target_session_ids))
        .order_by(FavoriteFolder.updated_at.desc())
    )

    # 手动按 media_id 去重，保留最新的
    folders_map = {}
    for row in rows.fetchall():
        fid, media_id, last_sync = row
        if media_id not in folders_map:
            folders_map[media_id] = (fid, last_sync)

    if not folders_map:
        return []

    folder_ids = [v[0] for v in folders_map.values()]

    # 4. 统计视频数量
    counts = await db.execute(
        select(FavoriteVideo.folder_id, func.count(func.distinct(FavoriteVideo.bvid)))
        .where(FavoriteVideo.folder_id.in_(folder_ids))
        .group_by(FavoriteVideo.folder_id)
    )
    count_map = {row[0]: row[1] for row in counts.fetchall()}

    result = []
    for media_id, (folder_id, last_sync_at) in folders_map.items():
        # 读取有效视频数（过滤失效后的口径）
        folder_row = await db.execute(
            select(FavoriteFolder.media_count).where(FavoriteFolder.id == folder_id)
        )
        media_count = folder_row.scalar()
        result.append(
            FolderStatus(
                media_id=media_id,
                indexed_count=count_map.get(folder_id, 0),
                media_count=media_count,
                last_sync_at=last_sync_at,
            )
        )
    return result


@router.post("/folders/sync", response_model=List[SyncResult])
async def sync_folders(
    request: Optional[SyncRequest] = None,
    session_id: Optional[str] = Query(None, description="会话ID"),
    db: AsyncSession = Depends(get_db),
):
    """同步收藏夹到向量库"""
    _raise_legacy_scoped_api_required()
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    cookies = session.get("cookies", {})
    user_info = session.get("user_info", {})

    bili = bilibili_service_from_cookies(cookies, BilibiliService)
    rag = get_rag_service()
    asr_service = ASRService()
    content_fetcher = ContentFetcher(bili, asr_service)

    try:
        folder_ids = request.folder_ids or []
        if not folder_ids:
            mid = user_info.get("mid") or cookies.get("DedeUserID")
            if not mid:
                raise HTTPException(status_code=400, detail="无法获取用户信息")
            folders = await bili.get_user_favorites(mid=mid)
            folder_ids = [folder.get("id") for folder in folders if folder.get("id")]

        results: List[SyncResult] = []
        for folder_id in folder_ids:
            try:
                result = await _sync_folder(
                    db,
                    bili,
                    rag,
                    content_fetcher,
                    session_id,
                    folder_id,
                )
                results.append(SyncResult(**result))
            except Exception as e:
                logger.error(f"同步收藏夹失败 [{folder_id}]: {e}")
                results.append(
                    SyncResult(
                        folder_id=folder_id,
                        total=0,
                        added=0,
                        removed=0,
                        indexed=0,
                        message=f"同步失败: {e}",
                        last_sync_at=None,
                    )
                )

        return results
    finally:
        await bili.close()


@router.post("/build")
async def build_knowledge_base(
    background_tasks: BackgroundTasks,
    request: Optional[BuildRequest] = None,
    session_id: Optional[str] = Query(None, description="会话ID"),
):
    """构建知识库（后台任务）"""
    _raise_legacy_scoped_api_required()
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")

    import uuid

    task_id = str(uuid.uuid4())

    build_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "初始化中...",
        "total_videos": 0,
        "processed_videos": 0,
        "message": "",
    }

    background_tasks.add_task(
        _build_knowledge_base_task,
        task_id,
        session_id,
        session,
        request.folder_ids,
        request.exclude_bvids or [],
    )

    return {"task_id": task_id, "message": "构建任务已启动"}


async def _build_knowledge_base_task(
    task_id: str,
    session_id: str,
    session: dict,
    folder_ids: List[int],
    exclude_bvids: List[str],
):
    """后台构建任务"""
    cookies = session.get("cookies", {})

    try:
        build_tasks[task_id]["status"] = "running"
        build_tasks[task_id]["current_step"] = "同步收藏夹..."

        bili = bilibili_service_from_cookies(cookies, BilibiliService)
        asr_service = ASRService()
        content_fetcher = ContentFetcher(bili, asr_service)
        rag = get_rag_service()

        try:
            total_folders = len(folder_ids)
            if total_folders == 0:
                build_tasks[task_id]["status"] = "completed"
                build_tasks[task_id]["progress"] = 100
                build_tasks[task_id]["message"] = "没有需要处理的收藏夹"
                return

            processed = 0
            total_added = 0
            total_removed = 0

            async with get_db_context() as db:
                for idx, folder_id in enumerate(folder_ids, start=1):
                    build_tasks[task_id]["current_step"] = f"同步收藏夹 {folder_id}"

                    def progress_cb(
                        title: str, processed_count: int = 0, total_count: int = 0
                    ):
                        build_tasks[task_id]["current_step"] = f"处理: {title}"
                        if total_count:
                            build_tasks[task_id]["total_videos"] = total_count
                        if processed_count:
                            build_tasks[task_id]["processed_videos"] = processed_count
                            if build_tasks[task_id]["total_videos"]:
                                build_tasks[task_id]["progress"] = int(
                                    (
                                        processed_count
                                        / build_tasks[task_id]["total_videos"]
                                    )
                                    * 100
                                )

                    result = await _sync_folder(
                        db,
                        bili,
                        rag,
                        content_fetcher,
                        session_id,
                        folder_id,
                        exclude_bvids=set(exclude_bvids),
                        progress_callback=progress_cb,
                    )

                    processed = idx
                    total_added += result["added"]
                    total_removed += result["removed"]

            build_tasks[task_id]["status"] = "completed"
            build_tasks[task_id]["progress"] = 100
            build_tasks[task_id]["processed_videos"] = total_folders
            build_tasks[task_id]["current_step"] = "完成"
            build_tasks[task_id][
                "message"
            ] = f"同步完成：新增 {total_added}，移除 {total_removed}"

            logger.info(f"知识库构建完成: 新增 {total_added}，移除 {total_removed}")
        finally:
            await bili.close()

    except Exception as e:
        logger.error(f"构建任务失败: {e}")
        build_tasks[task_id]["status"] = "failed"
        build_tasks[task_id]["message"] = str(e)


@router.get("/build/status/{task_id}", response_model=BuildStatus)
async def get_build_status(task_id: str):
    """获取构建任务状态"""
    _raise_legacy_scoped_api_required()
    if task_id not in build_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = build_tasks[task_id]
    return BuildStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        current_step=task["current_step"],
        total_videos=task["total_videos"],
        processed_videos=task["processed_videos"],
        message=task["message"],
    )


@router.delete("/clear", deprecated=True)
async def clear_knowledge_base():
    """清空知识库（已废弃：无多用户范围，请使用对应知识库的清空接口）"""
    _raise_legacy_scoped_api_required()
    logger.warning("调用了已废弃的全局 /knowledge/clear，建议迁移到知识库范围接口")
    try:
        rag = get_rag_service()
        rag.clear_collection()
        return {"message": "知识库已清空（此接口已废弃，请迁移到知识库范围接口）"}
    except Exception as e:
        logger.error(f"清空知识库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/video/{bvid}", deprecated=True)
async def delete_video_from_knowledge(bvid: str):
    """从知识库中删除指定视频（已废弃：无多用户范围，请使用知识库范围接口）"""
    _raise_legacy_scoped_api_required()
    logger.warning(
        "调用了已废弃的全局 /knowledge/video/{bvid}，建议迁移到知识库范围接口"
    )
    try:
        rag = get_rag_service()
        rag.delete_video(bvid)
        return {"message": f"已删除视频 {bvid}（此接口已废弃，请迁移到知识库范围接口）"}
    except Exception as e:
        logger.error(f"删除视频失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
