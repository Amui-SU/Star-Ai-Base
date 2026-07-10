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
from app.services.bilibili_multi_part import (
    detect_multi_part_video,
    extract_page_info,
    format_part_title,
    validate_page_selection,
    build_import_summary,
)
from app.schemas.multi_part_video import (
    DetectMultiPartResponse,
    ImportMultiPartRequest,
    ImportMultiPartResponse,
    VideoMultiPartInfo,
    VideoPageInfo,
)

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
    cid: int | None = None,
    page_number: int | None = None,
    part_title: str | None = None,
    total_parts: int | None = None,
    part_duration: int | None = None,
) -> None:
    await run_bilibili_video_import(
        task_id=task_id,
        bvid=bvid,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        cid=cid,
        page_number=page_number,
        part_title=part_title,
        total_parts=total_parts,
        part_duration=part_duration,
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


class DetectMultiPartRequest(BaseModel):
    """检测分P视频请求"""

    url: str = Field(..., min_length=3, description="B站视频URL")


@router.post("/detect-multi-part", response_model=DetectMultiPartResponse)
async def detect_multi_part(
    payload: DetectMultiPartRequest,
    current_user: SystemUser = Depends(get_current_user),
) -> DetectMultiPartResponse:
    """
    检测B站视频是否为分P视频，并返回分P信息
    """
    try:
        # 提取 bvid
        bvid = _extract_bvid(payload.url)
        if not bvid:
            return DetectMultiPartResponse(
                ok=False,
                message="无法从URL中提取BV号",
                multi_part_info=None,
            )

        # 获取视频信息
        bili = BilibiliService()
        try:
            video_info = await bili.get_video_info(bvid)
        finally:
            await bili.close()

        # 检测分P
        part_info = detect_multi_part_video(video_info)

        # 构建响应
        pages = [VideoPageInfo(**extract_page_info(p)) for p in part_info["pages"]]

        multi_part_info = VideoMultiPartInfo(
            bvid=bvid,
            title=video_info.get("title", ""),
            is_multi_part=part_info["is_multi_part"],
            total_parts=part_info["total_parts"],
            pages=pages,
            default_cid=part_info["default_cid"],
            description=video_info.get("desc"),
            owner_name=(video_info.get("owner") or {}).get("name"),
            pic_url=video_info.get("pic"),
        )

        if part_info["is_multi_part"]:
            message = f"检测到分P视频，共 {part_info['total_parts']} 个分P"
        else:
            message = "单P视频"

        return DetectMultiPartResponse(
            ok=True,
            message=message,
            multi_part_info=multi_part_info,
        )

    except Exception as exc:
        logger.error(f"检测分P视频失败: {exc}")
        return DetectMultiPartResponse(
            ok=False,
            message=f"检测失败: {str(exc)}",
            multi_part_info=None,
        )


@router.post("/multi-part", response_model=ImportMultiPartResponse)
async def import_multi_part(
    payload: ImportMultiPartRequest,
    background_tasks: BackgroundTasks,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ImportMultiPartResponse:
    """
    导入B站分P视频（支持批量导入多个分P）
    """
    try:
        # 提取 bvid
        bvid = _extract_bvid(payload.url)
        if not bvid:
            return ImportMultiPartResponse(
                ok=False,
                message="无法从URL中提取BV号",
            )

        # 验证知识库
        kb = await _get_owned_knowledge_base(
            db,
            current_user,
            current_workspace,
            payload.knowledge_base_id,
        )
        if not kb:
            return ImportMultiPartResponse(
                ok=False,
                message="知识库不存在或无权访问",
            )

        # 获取视频信息
        bili = BilibiliService()
        try:
            video_info = await bili.get_video_info(bvid)
        finally:
            await bili.close()

        # 检测分P
        part_info = detect_multi_part_video(video_info)
        base_title = video_info.get("title", bvid)

        # 确定要导入的分P
        if not payload.page_indices:
            # 空列表 = 导入全部
            selected_pages = part_info["pages"]
        else:
            # 验证选择
            is_valid, error_msg = validate_page_selection(
                payload.page_indices,
                part_info["total_parts"],
                allow_empty=True,
            )
            if not is_valid:
                return ImportMultiPartResponse(
                    ok=False,
                    message=error_msg,
                )

            # 提取选中的分P
            page_map = {p["page"]: p for p in part_info["pages"]}
            selected_pages = [
                page_map[i] for i in payload.page_indices if i in page_map
            ]

        if not selected_pages:
            return ImportMultiPartResponse(
                ok=False,
                message="没有要导入的分P",
            )

        # 为每个分P创建导入任务
        task_ids = []
        for page in selected_pages:
            page_info = extract_page_info(page)

            # 格式化标题
            if payload.title_format == "original":
                title = base_title
            elif payload.title_format == "custom" and payload.custom_title_prefix:
                title = f"{payload.custom_title_prefix} P{page_info['page']}"
                if page_info["part"]:
                    title += f": {page_info['part']}"
            else:  # auto
                title = format_part_title(
                    base_title,
                    page_info["page"],
                    page_info["part"],
                    part_info["total_parts"],
                )

            # 创建任务
            task = await create_ingestion_task(
                db=db,
                user_id=current_user.id,
                workspace_id=current_workspace.id,
                knowledge_base_id=kb.id,
                bvid=bvid,
                title=title,
                source_type="bilibili_video",
            )

            # 启动后台导入任务（带cid和分P元信息）
            background_tasks.add_task(
                _run_bilibili_video_import,
                task.task_id,
                bvid,
                current_workspace.id,
                kb.id,
                page_info["cid"],  # 传入具体的cid
                page_info["page"],  # 分P编号
                page_info["part"],  # 分P标题
                part_info["total_parts"],  # 总分P数
                page_info["duration"],  # 当前分P时长
            )

            task_ids.append(task.task_id)

        # 构建导入摘要
        import_summary = build_import_summary(
            base_title,
            [extract_page_info(p) for p in selected_pages],
            part_info["total_parts"],
        )

        return ImportMultiPartResponse(
            ok=True,
            message=f"已创建 {len(task_ids)} 个导入任务",
            bvid=bvid,
            total_selected=len(selected_pages),
            task_ids=task_ids,
            import_summary=import_summary,
        )

    except Exception as exc:
        logger.error(f"导入分P视频失败: {exc}")
        return ImportMultiPartResponse(
            ok=False,
            message=f"导入失败: {str(exc)}",
        )
