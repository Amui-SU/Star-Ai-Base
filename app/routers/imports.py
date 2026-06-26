import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_db_context
from app.dependencies import (
    get_current_user,
    get_current_workspace,
)
from app.models import FavoriteFolder, FavoriteVideo, IngestionTask, KnowledgeBase
from app.models import ContentSource, SystemUser, VideoCache, VideoContent, Workspace
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.rag_runtime import get_rag_service
from app.time_utils import utc_now

router = APIRouter(prefix="/imports", tags=["imports"])
_LOCAL_IMPORT_DIR = Path("data/local_imports")
_LOCAL_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".webm",
    ".avi",
    ".flv",
    ".wmv",
    ".mpeg",
    ".mpg",
}


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


def _is_video_upload(file: UploadFile) -> bool:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    return content_type.startswith("video/") or suffix in _LOCAL_VIDEO_EXTENSIONS


def _safe_upload_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in _LOCAL_VIDEO_EXTENSIONS else ".mp4"


def _local_video_id() -> str:
    return "LV" + uuid.uuid4().hex[:18].upper()


async def _get_owned_knowledge_base(
    db: AsyncSession,
    knowledge_base_id: int | None,
    workspace_id: int,
) -> KnowledgeBase:
    if not knowledge_base_id:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    knowledge_base = await db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    if knowledge_base.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return knowledge_base


async def _create_import_task(
    db: AsyncSession,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    user_id: int,
    current_step: str,
) -> str:
    task_id = str(uuid.uuid4())
    task = IngestionTask(
        task_id=task_id,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_binding_id=None,
        created_by=user_id,
        status="pending",
        progress=0,
        current_step=current_step,
        total_items=1,
        processed_items=0,
    )
    db.add(task)
    await db.commit()
    return task_id


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
                id="video_import",
                label="导入视频",
                description="支持视频 URL 或本地视频文件，直接导入到当前知识库",
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
    knowledge_base = await _get_owned_knowledge_base(
        db,
        payload.knowledge_base_id,
        current_workspace.id,
    )
    task_id = await _create_import_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {bvid}",
    )

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


@router.post("/local-video", response_model=ImportUrlResponse)
async def import_local_video(
    background_tasks: BackgroundTasks,
    knowledge_base_id: int = Form(...),
    title: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ImportUrlResponse:
    if not _is_video_upload(file):
        raise HTTPException(status_code=400, detail="请上传视频文件")

    knowledge_base = await _get_owned_knowledge_base(
        db,
        knowledge_base_id,
        current_workspace.id,
    )
    local_id = _local_video_id()
    video_title = (title or file.filename or local_id).strip() or local_id
    upload_dir = Path(_LOCAL_IMPORT_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{local_id}{_safe_upload_suffix(file.filename)}"
    try:
        with file_path.open("wb") as out_file:
            shutil.copyfileobj(file.file, out_file)
    finally:
        await file.close()

    task_id = await _create_import_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {video_title}",
    )

    background_tasks.add_task(
        _run_local_video_import,
        task_id=task_id,
        local_id=local_id,
        title=video_title,
        file_path=str(file_path),
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
    )

    return ImportUrlResponse(
        ok=True,
        status="pending",
        source_type="local_video",
        message="已创建本地视频导入任务",
        task_id=task_id,
        bvid=local_id,
    )


async def _update_import_task(task_id: str, **kwargs) -> None:
    async with get_db_context() as session:
        result = await session.execute(
            select(IngestionTask).where(IngestionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            for key, value in kwargs.items():
                setattr(task, key, value)
            await session.commit()


def _delete_existing_import_vectors(
    rag,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> None:
    try:
        rag.delete_video_in_knowledge_base(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
    except Exception as exc:
        logger.warning(
            "Import vector cleanup failed "
            f"[workspace={workspace_id}, knowledge_base={knowledge_base_id}, "
            f"bvid={bvid}]: {exc}"
        )


def _cleanup_local_upload(file_path: str) -> None:
    try:
        upload_path = Path(file_path)
        if upload_path.exists():
            upload_path.unlink()
    except Exception as exc:
        logger.warning(f"Local upload cleanup failed [{file_path}]: {exc}")


async def _store_imported_video_content(
    *,
    content: VideoContent,
    workspace_id: int,
    knowledge_base_id: int,
    description: str | None = None,
    owner_name: str | None = None,
    owner_mid: int | None = None,
    duration: int | None = None,
    pic_url: str | None = None,
    folder_title: str = "单条视频导入",
) -> None:
    async with get_db_context() as db:
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.bvid == content.bvid)
            .where(VideoCache.workspace_id == workspace_id)
            .where(VideoCache.knowledge_base_id == knowledge_base_id)
            .where(VideoCache.source_binding_id.is_(None))
        )
        cache = result.scalar_one_or_none()
        if cache is None:
            cache = VideoCache(
                bvid=content.bvid,
                title=content.title,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=None,
                is_processed=True,
            )
            db.add(cache)
        cache.title = content.title
        cache.description = description
        cache.owner_name = owner_name
        cache.owner_mid = owner_mid
        cache.duration = duration
        cache.pic_url = pic_url
        cache.content = content.content
        cache.content_source = content.source.value
        cache.outline_json = content.outline
        cache.is_processed = True
        cache.workspace_id = workspace_id
        cache.knowledge_base_id = knowledge_base_id
        cache.source_binding_id = None

        folder_result = await db.execute(
            select(FavoriteFolder)
            .where(FavoriteFolder.workspace_id == workspace_id)
            .where(FavoriteFolder.knowledge_base_id == knowledge_base_id)
            .where(FavoriteFolder.media_id == 0)
            .where(FavoriteFolder.title == folder_title)
        )
        folder = folder_result.scalar_one_or_none()
        if folder is None:
            folder = FavoriteFolder(
                session_id="",
                media_id=0,
                title=folder_title,
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
            .where(FavoriteVideo.bvid == content.bvid)
        )
        if exists.scalar_one_or_none() is None:
            db.add(
                FavoriteVideo(
                    folder_id=folder.id,
                    bvid=content.bvid,
                    is_selected=True,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=None,
                )
            )
            folder.media_count = (folder.media_count or 0) + 1
        folder.last_sync_at = utc_now()
        await db.commit()


async def _run_bilibili_video_import(
    task_id: str,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
) -> None:
    bili = BilibiliService()
    asr = ASRService()
    fetcher = ContentFetcher(bili, asr)
    try:
        rag = get_rag_service()
        await _update_import_task(
            task_id,
            status="running",
            current_step="获取视频信息...",
            progress=12,
        )
        info = await bili.get_video_info(bvid)
        title = info.get("title") or bvid
        cid = info.get("cid")

        await _update_import_task(task_id, current_step="提取视频内容...", progress=36)
        content = await fetcher.fetch_content(bvid, cid=cid, title=title)

        await _store_imported_video_content(
            content=content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            description=info.get("desc"),
            owner_name=(info.get("owner") or {}).get("name"),
            owner_mid=(info.get("owner") or {}).get("mid"),
            duration=info.get("duration"),
            pic_url=info.get("pic"),
        )

        await _update_import_task(task_id, current_step="写入向量索引...", progress=76)
        _delete_existing_import_vectors(
            rag,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=bvid,
        )
        rag.add_video_content(
            content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        await _update_import_task(
            task_id,
            status="completed",
            progress=100,
            processed_items=1,
            current_step="导入完成",
            error_message=None,
        )
    except Exception as exc:
        await _update_import_task(
            task_id,
            status="failed",
            current_step="导入失败",
            error_message=str(exc),
        )
    finally:
        await bili.close()


async def _run_local_video_import(
    task_id: str,
    local_id: str,
    title: str,
    file_path: str,
    workspace_id: int,
    knowledge_base_id: int,
) -> None:
    asr = ASRService()
    try:
        rag = get_rag_service()
        await _update_import_task(
            task_id,
            status="running",
            current_step="转写本地视频...",
            progress=28,
        )
        transcript = await asr.transcribe_local_file(file_path)
        if not transcript or len(transcript.strip()) < 10:
            raise ValueError("未能从本地视频中识别到有效文本")

        content = VideoContent(
            bvid=local_id,
            title=title,
            content=transcript.strip(),
            source=ContentSource.ASR,
        )

        await _store_imported_video_content(
            content=content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            description=f"本地视频文件：{Path(file_path).name}",
        )

        await _update_import_task(task_id, current_step="写入向量索引...", progress=76)
        _delete_existing_import_vectors(
            rag,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            bvid=local_id,
        )
        rag.add_video_content(
            content,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        await _update_import_task(
            task_id,
            status="completed",
            progress=100,
            processed_items=1,
            current_step="导入完成",
            error_message=None,
        )
    except Exception as exc:
        await _update_import_task(
            task_id,
            status="failed",
            current_step="导入失败",
            error_message=str(exc),
        )
    finally:
        _cleanup_local_upload(file_path)
