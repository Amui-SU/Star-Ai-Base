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
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
)
from app.models import KnowledgeBase
from app.models import SystemUser, Workspace
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.ingestion_tasks import create_ingestion_task, update_ingestion_task
from app.services.import_tasks import (
    cleanup_local_upload,
    delete_existing_import_vectors,
    run_bilibili_video_import,
    run_local_video_import,
    store_imported_video_content,
)
from app.services.rag_runtime import get_rag_service

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


def _delete_existing_import_vectors(
    rag,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str,
) -> None:
    return delete_existing_import_vectors(
        rag,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        bvid=bvid,
        warning_logger=logger.warning,
    )


def _cleanup_local_upload(file_path: str) -> None:
    return cleanup_local_upload(file_path, warning_logger=logger.warning)


_store_imported_video_content = store_imported_video_content


async def _run_bilibili_video_import(
    task_id: str,
    bvid: str,
    workspace_id: int,
    knowledge_base_id: int,
) -> None:
    await run_bilibili_video_import(
        task_id,
        bvid,
        workspace_id,
        knowledge_base_id,
        bilibili_service_class=BilibiliService,
        asr_service_class=ASRService,
        content_fetcher_class=ContentFetcher,
        rag_factory=get_rag_service,
        update_task=update_ingestion_task,
        store_content=_store_imported_video_content,
        delete_vectors=_delete_existing_import_vectors,
    )


async def _run_local_video_import(
    task_id: str,
    local_id: str,
    title: str,
    file_path: str,
    workspace_id: int,
    knowledge_base_id: int,
) -> None:
    await run_local_video_import(
        task_id,
        local_id,
        title,
        file_path,
        workspace_id,
        knowledge_base_id,
        asr_service_class=ASRService,
        rag_factory=get_rag_service,
        update_task=update_ingestion_task,
        store_content=_store_imported_video_content,
        delete_vectors=_delete_existing_import_vectors,
        cleanup_upload=_cleanup_local_upload,
    )


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
    task_id = await create_ingestion_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {bvid}",
        total_items=1,
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

    task_id = await create_ingestion_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {video_title}",
        total_items=1,
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
