"""Request-level runtime helpers for import routes."""

import re
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase

DEFAULT_LOCAL_IMPORT_DIR = Path("data/local_imports")
LOCAL_VIDEO_EXTENSIONS = {
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

_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")


def detect_import_source_type(url: str, requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    host = urlparse(url).netloc.lower()
    if "bilibili.com" in host or "b23.tv" in host or _BVID_RE.search(url):
        return "bilibili_video"
    if "douyin.com" in host:
        return "douyin"
    return "url"


def extract_bilibili_bvid(url: str) -> str | None:
    match = _BVID_RE.search(url)
    return match.group(1) if match else None


def is_video_upload(file: Any) -> bool:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    return content_type.startswith("video/") or suffix in LOCAL_VIDEO_EXTENSIONS


def safe_upload_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in LOCAL_VIDEO_EXTENSIONS else ".mp4"


def local_video_id() -> str:
    return "LV" + uuid.uuid4().hex[:18].upper()


async def get_owned_knowledge_base(
    db: AsyncSession,
    knowledge_base_id: int | None,
    workspace_id: int,
    *,
    knowledge_base_model: type[KnowledgeBase] = KnowledgeBase,
) -> KnowledgeBase:
    if not knowledge_base_id:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    knowledge_base = await db.get(knowledge_base_model, knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=400, detail="请先选择知识库")
    if knowledge_base.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return knowledge_base


async def prepare_bilibili_import_request(
    *,
    url: str,
    requested_source_type: str,
    knowledge_base_id: int | None,
    background_tasks: Any,
    current_user: Any,
    current_workspace: Any,
    db: AsyncSession,
    run_bilibili_video_import: Callable[..., Any],
    create_task: Callable[..., Any],
) -> dict[str, Any]:
    source_type = detect_import_source_type(url, requested_source_type)
    if source_type != "bilibili_video":
        return {
            "ok": False,
            "status": "unsupported",
            "source_type": source_type,
            "message": "该导入方式入口已保留，解析与入库处理器尚未接入。",
        }

    bvid = extract_bilibili_bvid(url)
    if not bvid:
        raise HTTPException(status_code=400, detail="未识别到 B 站 BV 号")

    knowledge_base = await get_owned_knowledge_base(
        db,
        knowledge_base_id,
        current_workspace.id,
    )
    task_id = await create_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {bvid}",
        total_items=1,
    )
    background_tasks.add_task(
        run_bilibili_video_import,
        task_id=task_id,
        bvid=bvid,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
    )
    return {
        "ok": True,
        "status": "pending",
        "source_type": source_type,
        "message": "已创建视频导入任务",
        "task_id": task_id,
        "bvid": bvid,
    }


async def prepare_local_video_import_request(
    *,
    knowledge_base_id: int,
    title: str | None,
    file: Any,
    background_tasks: Any,
    current_user: Any,
    current_workspace: Any,
    db: AsyncSession,
    run_local_video_import: Callable[..., Any],
    create_task: Callable[..., Any],
    local_import_dir: Path | str = DEFAULT_LOCAL_IMPORT_DIR,
    local_video_id_factory: Callable[[], str] = local_video_id,
) -> dict[str, Any]:
    if not is_video_upload(file):
        raise HTTPException(status_code=400, detail="请上传视频文件")

    knowledge_base = await get_owned_knowledge_base(
        db,
        knowledge_base_id,
        current_workspace.id,
    )
    local_id = local_video_id_factory()
    video_title = (title or file.filename or local_id).strip() or local_id
    upload_dir = Path(local_import_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{local_id}{safe_upload_suffix(file.filename)}"
    try:
        with file_path.open("wb") as out_file:
            shutil.copyfileobj(file.file, out_file)
    finally:
        await file.close()

    task_id = await create_task(
        db,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        user_id=current_user.id,
        current_step=f"准备导入 {video_title}",
        total_items=1,
    )
    background_tasks.add_task(
        run_local_video_import,
        task_id=task_id,
        local_id=local_id,
        title=video_title,
        file_path=str(file_path),
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
    )
    return {
        "ok": True,
        "status": "pending",
        "source_type": "local_video",
        "message": "已创建本地视频导入任务",
        "task_id": task_id,
        "bvid": local_id,
    }
