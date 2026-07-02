"""
Bilibili RAG 知识库系统

知识库路由 - 构建和管理知识库
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.knowledge_legacy_runtime import (
    build_tasks,
    clear_legacy_knowledge_base,
    delete_legacy_video_from_knowledge,
    get_collection_stats_without_embeddings,
    get_legacy_build_status,
    get_legacy_folder_status,
    run_legacy_build_task,
    start_legacy_build_task_for_session,
    sync_legacy_folders,
)

router = APIRouter(prefix="/knowledge", tags=["知识库"])
LEGACY_SCOPED_API_DETAIL = "旧全局接口已禁用，请使用 /knowledge-bases/* 范围化 API。"


def _raise_legacy_scoped_api_required() -> None:
    raise HTTPException(status_code=410, detail=LEGACY_SCOPED_API_DETAIL)


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
    return [
        FolderStatus(**item) for item in await get_legacy_folder_status(session_id, db)
    ]


@router.post("/folders/sync", response_model=List[SyncResult])
async def sync_folders(
    request: Optional[SyncRequest] = None,
    session_id: Optional[str] = Query(None, description="会话ID"),
    db: AsyncSession = Depends(get_db),
):
    """同步收藏夹到向量库"""
    _raise_legacy_scoped_api_required()
    return [
        SyncResult(**item)
        for item in await sync_legacy_folders(
            request,
            session_id=session_id,
            db=db,
        )
    ]


@router.post("/build")
async def build_knowledge_base(
    background_tasks: BackgroundTasks,
    request: Optional[BuildRequest] = None,
    session_id: Optional[str] = Query(None, description="会话ID"),
):
    """构建知识库（后台任务）"""
    _raise_legacy_scoped_api_required()
    return await start_legacy_build_task_for_session(
        background_tasks,
        request,
        session_id=session_id,
        task_runner=run_legacy_build_task,
    )


@router.get("/build/status/{task_id}", response_model=BuildStatus)
async def get_build_status(task_id: str):
    """获取构建任务状态"""
    _raise_legacy_scoped_api_required()
    return BuildStatus(**get_legacy_build_status(task_id))


@router.delete("/clear", deprecated=True)
async def clear_knowledge_base():
    """清空知识库（已废弃：无多用户范围，请使用对应知识库的清空接口）"""
    _raise_legacy_scoped_api_required()
    return clear_legacy_knowledge_base()


@router.delete("/video/{bvid}", deprecated=True)
async def delete_video_from_knowledge(bvid: str):
    """从知识库中删除指定视频（已废弃：无多用户范围，请使用知识库范围接口）"""
    _raise_legacy_scoped_api_required()
    return delete_legacy_video_from_knowledge(bvid)
