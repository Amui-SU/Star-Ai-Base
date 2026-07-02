"""Runtime helpers for deprecated global knowledge routes."""

import uuid
from typing import Any

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import FavoriteFolder, FavoriteVideo, UserSession
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.services.content_fetcher import ContentFetcher
from app.services.folder_ingestion import sync_folder as _sync_folder
from app.services.legacy_bilibili_sessions import get_session
from app.services.rag_runtime import get_rag_service


build_tasks: dict[str, dict[str, Any]] = {}


def get_collection_stats_without_embeddings(
    collection_name: str = "bilibili_videos",
    *,
    chroma_directory: str | None = None,
    warning_logger=logger.warning,
) -> dict:
    try:
        import chromadb

        client = chromadb.PersistentClient(
            path=chroma_directory or settings.chroma_persist_directory
        )
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
    except Exception as exc:
        warning_logger(f"Failed to read legacy knowledge stats: {exc}")
        return {
            "total_chunks": 0,
            "total_videos": 0,
            "collection_name": collection_name,
        }


async def get_legacy_folder_status(session_id: str | None, db: AsyncSession) -> list:
    result = await db.execute(
        select(UserSession.bili_mid).where(UserSession.session_id == session_id)
    )
    mid = result.scalar()

    target_session_ids = [session_id]
    if mid:
        result = await db.execute(
            select(UserSession.session_id).where(UserSession.bili_mid == mid)
        )
        target_session_ids = [row[0] for row in result.fetchall()]

    rows = await db.execute(
        select(FavoriteFolder.id, FavoriteFolder.media_id, FavoriteFolder.last_sync_at)
        .where(FavoriteFolder.session_id.in_(target_session_ids))
        .order_by(FavoriteFolder.updated_at.desc())
    )

    folders_map = {}
    for row in rows.fetchall():
        folder_id, media_id, last_sync = row
        if media_id not in folders_map:
            folders_map[media_id] = (folder_id, last_sync)

    if not folders_map:
        return []

    folder_ids = [value[0] for value in folders_map.values()]
    counts = await db.execute(
        select(FavoriteVideo.folder_id, func.count(func.distinct(FavoriteVideo.bvid)))
        .where(FavoriteVideo.folder_id.in_(folder_ids))
        .group_by(FavoriteVideo.folder_id)
    )
    count_map = {row[0]: row[1] for row in counts.fetchall()}

    statuses = []
    for media_id, (folder_id, last_sync_at) in folders_map.items():
        folder_row = await db.execute(
            select(FavoriteFolder.media_count).where(FavoriteFolder.id == folder_id)
        )
        statuses.append(
            {
                "media_id": media_id,
                "indexed_count": count_map.get(folder_id, 0),
                "media_count": folder_row.scalar(),
                "last_sync_at": last_sync_at,
            }
        )
    return statuses


async def sync_legacy_folders(
    request,
    *,
    session_id: str | None,
    db: AsyncSession,
    get_session_func=get_session,
    service_from_cookies=bilibili_service_from_cookies,
    bilibili_service_cls=BilibiliService,
    rag_service_factory=get_rag_service,
    asr_service_factory=ASRService,
    content_fetcher_cls=ContentFetcher,
    sync_folder_func=_sync_folder,
    error_logger=logger.error,
) -> list:
    session = await get_session_func(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in or session expired")

    cookies = session.get("cookies", {})
    user_info = session.get("user_info", {})

    bili = service_from_cookies(cookies, bilibili_service_cls)
    rag = rag_service_factory()
    content_fetcher = content_fetcher_cls(bili, asr_service_factory())

    try:
        folder_ids = (request.folder_ids if request else None) or []
        if not folder_ids:
            mid = user_info.get("mid") or cookies.get("DedeUserID")
            if not mid:
                raise HTTPException(status_code=400, detail="Unable to read user info")
            folders = await bili.get_user_favorites(mid=mid)
            folder_ids = [folder.get("id") for folder in folders if folder.get("id")]

        results = []
        for folder_id in folder_ids:
            try:
                result = await sync_folder_func(
                    db,
                    bili,
                    rag,
                    content_fetcher,
                    session_id,
                    folder_id,
                )
                results.append(result)
            except Exception as exc:
                error_logger(f"Legacy folder sync failed [{folder_id}]: {exc}")
                results.append(
                    {
                        "folder_id": folder_id,
                        "total": 0,
                        "added": 0,
                        "removed": 0,
                        "indexed": 0,
                        "message": f"Sync failed: {exc}",
                        "last_sync_at": None,
                    }
                )
        return results
    finally:
        await bili.close()


def start_legacy_build_task(
    background_tasks,
    request,
    *,
    session_id: str | None,
    session: dict,
    task_runner=None,
) -> dict:
    task_id = str(uuid.uuid4())
    task_runner = task_runner or run_legacy_build_task
    folder_ids = (request.folder_ids if request else None) or []
    exclude_bvids = (request.exclude_bvids if request else None) or []

    build_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": "Initializing...",
        "total_videos": 0,
        "processed_videos": 0,
        "message": "",
    }
    background_tasks.add_task(
        task_runner,
        task_id,
        session_id,
        session,
        folder_ids,
        exclude_bvids,
    )
    return {"task_id": task_id, "message": "Build task started"}


async def start_legacy_build_task_for_session(
    background_tasks,
    request,
    *,
    session_id: str | None,
    get_session_func=get_session,
    task_runner=None,
) -> dict:
    session = await get_session_func(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in or session expired")
    return start_legacy_build_task(
        background_tasks,
        request,
        session_id=session_id,
        session=session,
        task_runner=task_runner,
    )


async def run_legacy_build_task(
    task_id: str,
    session_id: str,
    session: dict,
    folder_ids: list[int],
    exclude_bvids: list[str],
    *,
    service_from_cookies=bilibili_service_from_cookies,
    bilibili_service_cls=BilibiliService,
    asr_service_factory=ASRService,
    content_fetcher_cls=ContentFetcher,
    rag_service_factory=get_rag_service,
    db_context_factory=get_db_context,
    sync_folder_func=_sync_folder,
    error_logger=logger.error,
    info_logger=logger.info,
) -> None:
    cookies = session.get("cookies", {})
    try:
        build_tasks[task_id]["status"] = "running"
        build_tasks[task_id]["current_step"] = "Syncing folders..."

        bili = service_from_cookies(cookies, bilibili_service_cls)
        content_fetcher = content_fetcher_cls(bili, asr_service_factory())
        rag = rag_service_factory()

        try:
            total_folders = len(folder_ids)
            if total_folders == 0:
                build_tasks[task_id]["status"] = "completed"
                build_tasks[task_id]["progress"] = 100
                build_tasks[task_id]["message"] = "No folders to process"
                return

            total_added = 0
            total_removed = 0
            async with db_context_factory() as db:
                for idx, folder_id in enumerate(folder_ids, start=1):
                    build_tasks[task_id]["current_step"] = f"Syncing folder {folder_id}"

                    def progress_cb(
                        title: str, processed_count: int = 0, total_count: int = 0
                    ):
                        build_tasks[task_id]["current_step"] = f"Processing: {title}"
                        if total_count:
                            build_tasks[task_id]["total_videos"] = total_count
                        if processed_count:
                            build_tasks[task_id]["processed_videos"] = processed_count
                            if build_tasks[task_id]["total_videos"]:
                                build_tasks[task_id]["progress"] = int(
                                    processed_count
                                    / build_tasks[task_id]["total_videos"]
                                    * 100
                                )

                    result = await sync_folder_func(
                        db,
                        bili,
                        rag,
                        content_fetcher,
                        session_id,
                        folder_id,
                        exclude_bvids=set(exclude_bvids),
                        progress_callback=progress_cb,
                    )
                    total_added += result["added"]
                    total_removed += result["removed"]

            build_tasks[task_id]["status"] = "completed"
            build_tasks[task_id]["progress"] = 100
            build_tasks[task_id]["processed_videos"] = total_folders
            build_tasks[task_id]["current_step"] = "Completed"
            build_tasks[task_id][
                "message"
            ] = f"Sync completed: added {total_added}, removed {total_removed}"
            info_logger(
                f"Legacy knowledge build completed: added {total_added}, "
                f"removed {total_removed}"
            )
        finally:
            await bili.close()
    except Exception as exc:
        error_logger(f"Legacy build task failed: {exc}")
        build_tasks[task_id]["status"] = "failed"
        build_tasks[task_id]["message"] = str(exc)


def get_legacy_build_status(task_id: str) -> dict:
    if task_id not in build_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = build_tasks[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "total_videos": task["total_videos"],
        "processed_videos": task["processed_videos"],
        "message": task["message"],
    }


def clear_legacy_knowledge_base(
    *,
    rag_service_factory=get_rag_service,
    warning_logger=logger.warning,
    error_logger=logger.error,
) -> dict:
    warning_logger(
        "Deprecated global /knowledge/clear called; migrate to scoped endpoints"
    )
    try:
        rag = rag_service_factory()
        rag.clear_collection()
        return {"message": "Knowledge base cleared by deprecated global endpoint"}
    except Exception as exc:
        error_logger(f"Failed to clear legacy knowledge base: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def delete_legacy_video_from_knowledge(
    bvid: str,
    *,
    rag_service_factory=get_rag_service,
    warning_logger=logger.warning,
    error_logger=logger.error,
) -> dict:
    warning_logger(
        "Deprecated global /knowledge/video/{bvid} called; migrate to scoped endpoints"
    )
    try:
        rag = rag_service_factory()
        rag.delete_video(bvid)
        return {"message": f"Deleted video {bvid} by deprecated global endpoint"}
    except Exception as exc:
        error_logger(f"Failed to delete legacy knowledge video: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
