from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
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
from app.models import SystemUser, Workspace
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.ingestion_tasks import create_ingestion_task, update_ingestion_task
from app.services.import_request_runtime import (
    DEFAULT_LOCAL_IMPORT_DIR,
    detect_import_source_type as _detect_source_type,
    extract_bilibili_bvid as _extract_bvid,
    get_owned_knowledge_base as _get_owned_knowledge_base,
    is_video_upload as _is_video_upload,
    local_video_id as _local_video_id,
    prepare_bilibili_import_request,
    prepare_local_video_import_request,
    safe_upload_suffix as _safe_upload_suffix,
)
from app.services.import_tasks import (
    cleanup_local_upload,
    delete_existing_import_vectors,
    run_bilibili_video_import,
    run_local_video_import,
    store_imported_video_content,
)
from app.services.rag_runtime import get_rag_service

router = APIRouter(prefix="/imports", tags=["imports"])
_LOCAL_IMPORT_DIR = DEFAULT_LOCAL_IMPORT_DIR


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
    return ImportUrlResponse(
        **await prepare_bilibili_import_request(
            url=payload.url,
            requested_source_type=payload.source_type,
            knowledge_base_id=payload.knowledge_base_id,
            background_tasks=background_tasks,
            current_user=current_user,
            current_workspace=current_workspace,
            db=db,
            run_bilibili_video_import=_run_bilibili_video_import,
            create_task=create_ingestion_task,
        )
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
    return ImportUrlResponse(
        **await prepare_local_video_import_request(
            knowledge_base_id=knowledge_base_id,
            title=title,
            file=file,
            background_tasks=background_tasks,
            current_user=current_user,
            current_workspace=current_workspace,
            db=db,
            run_local_video_import=_run_local_video_import,
            create_task=create_ingestion_task,
            local_import_dir=_LOCAL_IMPORT_DIR,
            local_video_id_factory=_local_video_id,
        )
    )
