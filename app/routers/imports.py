import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_db_context
from app.dependencies import (
    get_current_user,
    get_current_workspace,
)
from app.models import (
    ContentSource,
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    KnowledgeBase,
    SourceBinding,
    SystemUser,
    VideoCache,
    Workspace,
)
from app.routers.knowledge import get_rag_service
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportMethod(BaseModel):
    id: str
    label: str
    description: str
    status: str
    level: int = 1


class ImportMethodsResponse(BaseModel):
    methods: list[ImportMethod]


class ImportUrlRequest(BaseModel):
    url: str = Field(..., min_length=3)
    source_type: str = "auto"
    knowledge_base_id: int | None = None


class ImportUrlResponse(BaseModel):
    ok: bool
    status: str
    source_type: str
    message: str
    task_id: str | None = None
    bvid: str | None = None


_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")


def _detect_source_type(url: str, requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    host = urlparse(url).netloc.lower()
    if "bilibili.com" in host or "b23.tv" in host or _BVID_RE.search(url):
        return "bilibili_video"
    if "douyin.com" in host:
        return "douyin"
    return "url"


def _extract_bvid(url: str) -> str | None:
    match = _BVID_RE.search(url)
    return match.group(1) if match else None


@router.get("/methods", response_model=ImportMethodsResponse)
async def list_import_methods() -> ImportMethodsResponse:
    return ImportMethodsResponse(
        methods=[
            ImportMethod(
                id="bilibili_favorites",
                label="B 站收藏夹",
                description="扫码绑定账号后导入收藏夹资料",
                status="available",
                level=2,
            ),
            ImportMethod(
                id="video_url",
                label="视频 URL",
                description="粘贴 B 站视频链接，直接导入到当前知识库",
                status="available",
            ),
            ImportMethod(
                id="douyin",
                label="抖音",
                description="入口已预留，解析与入库处理器待接入",
                status="coming_soon",
            ),
            ImportMethod(
                id="generic_url",
                label="网页 / 其他链接",
                description="入口已预留，后续接入网页与更多平台",
                status="coming_soon",
            ),
        ]
    )


@router.post("/url", response_model=ImportUrlResponse)
async def import_url(
    payload: ImportUrlRequest,
    background_tasks: BackgroundTasks,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ImportUrlResponse:
    source_type = _detect_source_type(payload.url, payload.source_type)
    if source_type != "bilibili_video":
        return ImportUrlResponse(
            ok=False,
            status="unsupported",
            source_type=source_type,
            message="该导入方式入口已保留，解析与入库处理器尚未接入。",
        )

    bvid = _extract_bvid(payload.url)
    if not bvid:
        raise HTTPException(status_code=400, detail="未识别到 B 站 BV 号")
    if not payload.knowledge_base_id:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    knowledge_base = await db.get(KnowledgeBase, payload.knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    if knowledge_base.workspace_id != current_workspace.id:
        raise HTTPException(status_code=404, detail="知识库不存在")

    task_id = str(uuid.uuid4())
    task = IngestionTask(
        task_id=task_id,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=None,
        created_by=current_user.id,
        status="pending",
        progress=0,
        current_step=f"准备导入 {bvid}",
        total_items=1,
        processed_items=0,
    )
    db.add(task)
    await db.commit()

    background_tasks.add_task(
        _run_bilibili_video_import,
        task_id=task_id,
        bvid=bvid,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
    )

    return ImportUrlResponse(
        ok=True,
        status="pending",
        source_type=source_type,
        message="已创建视频导入任务",
        task_id=task_id,
        bvid=bvid,
    )


async def _run_bilibili_video_import(
    task_id: str,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
) -> None:
    async def update_task(**kwargs):
        async with get_db_context() as session:
            result = await session.execute(
                select(IngestionTask).where(IngestionTask.task_id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                for key, value in kwargs.items():
                    setattr(task, key, value)
                await session.commit()

    bili = BilibiliService()
    asr = ASRService()
    fetcher = ContentFetcher(bili, asr)
    rag = get_rag_service()
    try:
        await update_task(status="running", current_step="获取视频信息...", progress=12)
        info = await bili.get_video_info(bvid)
        title = info.get("title") or bvid
        cid = info.get("cid")

        await update_task(current_step="提取视频内容...", progress=36)
        content = await fetcher.fetch_content(bvid, cid=cid, title=title)

        async with get_db_context() as db:
            result = await db.execute(select(VideoCache).where(VideoCache.bvid == bvid))
            cache = result.scalar_one_or_none()
            if cache is None:
                cache = VideoCache(
                    bvid=bvid,
                    title=title,
                    description=info.get("desc"),
                    owner_name=(info.get("owner") or {}).get("name"),
                    owner_mid=(info.get("owner") or {}).get("mid"),
                    duration=info.get("duration"),
                    pic_url=info.get("pic"),
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    is_processed=True,
                )
                db.add(cache)
            cache.title = title
            cache.content = content.content
            cache.content_source = content.source.value
            cache.outline_json = content.outline
            cache.is_processed = True
            cache.workspace_id = workspace_id
            cache.knowledge_base_id = knowledge_base_id

            folder_result = await db.execute(
                select(FavoriteFolder)
                .where(FavoriteFolder.workspace_id == workspace_id)
                .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
                .where(FavoriteFolder.media_id == 0)
                .where(FavoriteFolder.title == "单条视频导入")
            )
            folder = folder_result.scalar_one_or_none()
            if folder is None:
                folder = FavoriteFolder(
                    session_id="",
                    media_id=0,
                    title="单条视频导入",
                    media_count=0,
                    is_selected=True,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=None,
                )
                db.add(folder)
                await db.flush()

            exists = await db.execute(
                select(FavoriteVideo.id)
                .where(FavoriteVideo.folder_id == folder.id)
                .where(FavoriteVideo.bvid == bvid)
            )
            if exists.scalar_one_or_none() is None:
                db.add(
                    FavoriteVideo(
                        folder_id=folder.id,
                        bvid=bvid,
                        is_selected=True,
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base_id,
                        source_binding_id=None,
                    )
                )
                folder.media_count = (folder.media_count or 0) + 1
            folder.last_sync_at = datetime.now(timezone.utc)
            await db.commit()

        await update_task(current_step="写入向量索引...", progress=76)
        try:
            rag.delete_video(bvid)
        except Exception:
            pass
        chunks = rag.add_video_content(
            content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        await update_task(
            status="completed",
            progress=100,
            processed_items=1,
            current_step="导入完成",
            error_message=None,
        )
    except Exception as exc:
        await update_task(
            status="failed",
            current_step="导入失败",
            error_message=str(exc),
        )
    finally:
        await bili.close()
