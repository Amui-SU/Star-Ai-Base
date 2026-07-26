"""
Bilibili RAG 知识库系统

知识库路由 - 旧全局接口已禁用，仅保留 410 Gone 提示
"""

from fastapi import APIRouter

from app.services.legacy_api import raise_legacy_api_gone

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/stats")
async def get_knowledge_stats():
    """获取知识库统计信息（已禁用）"""
    raise_legacy_api_gone()


@router.get("/folders/status")
async def get_folder_status():
    """获取收藏夹入库状态（已禁用）"""
    raise_legacy_api_gone()


@router.post("/folders/sync")
async def sync_folders():
    """同步收藏夹到向量库（已禁用）"""
    raise_legacy_api_gone()


@router.post("/build")
async def build_knowledge_base():
    """构建知识库（已禁用）"""
    raise_legacy_api_gone()


@router.get("/build/status/{task_id}")
async def get_build_status(task_id: str):
    """获取构建任务状态（已禁用）"""
    raise_legacy_api_gone()


@router.delete("/clear", deprecated=True)
async def clear_knowledge_base():
    """清空知识库（已禁用）"""
    raise_legacy_api_gone()


@router.delete("/video/{bvid}", deprecated=True)
async def delete_video_from_knowledge(bvid: str):
    """从知识库中删除指定视频（已禁用）"""
    raise_legacy_api_gone()
