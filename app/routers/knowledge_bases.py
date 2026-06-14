import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
)
from app.models import (
    ChatResponse,
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    KnowledgeBase,
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    KnowledgeScopeOptionsResponse,
    SourceBinding,
    SourceCredential,
    SystemUser,
    VideoCache,
    VideoTitleOverride,
    Workspace,
)
from app.routers.knowledge import _sync_folder, get_rag_service
from app.security import decrypt_text
from app.services.asr import ASRService
from app.services.bilibili import BilibiliService
from app.services.content_fetcher import ContentFetcher
from app.services.knowledge_scope import (
    InvalidKnowledgeScope,
    list_scope_options,
    resolve_scope_bvids,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def _response(knowledge_base: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        name=knowledge_base.name,
        description=knowledge_base.description,
    )


def _search_result(document) -> KnowledgeBaseSearchResult:
    metadata = document.metadata or {}
    return KnowledgeBaseSearchResult(
        content=document.page_content,
        bvid=metadata.get("bvid"),
        title=metadata.get("title"),
        url=metadata.get("url"),
    )


def _source_from_document(document) -> dict:
    metadata = document.metadata or {}
    bvid = metadata.get("bvid")
    return {
        "bvid": bvid,
        "title": metadata.get("title") or bvid or "Untitled",
        "url": metadata.get("url") or f"https://www.bilibili.com/video/{bvid or ''}",
    }


def _answer_from_documents(question: str, documents: list) -> ChatResponse:
    if not documents:
        return ChatResponse(
            answer="当前知识库中没有找到相关内容。",
            sources=[],
        )
    context = "\n\n".join(document.page_content for document in documents)
    return ChatResponse(
        answer=f"基于当前知识库内容，关于“{question}”可以参考：\n\n{context}",
        sources=[_source_from_document(document) for document in documents],
    )


async def _resolve_request_scope(
    db: AsyncSession,
    *,
    knowledge_base_id: int,
    folder_ids: list[int] | None,
    bvids: list[str] | None,
) -> list[str] | None:
    try:
        return await resolve_scope_bvids(
            db,
            knowledge_base_id=knowledge_base_id,
            folder_media_ids=folder_ids,
            requested_bvids=bvids,
        )
    except InvalidKnowledgeScope as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseResponse]:
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.workspace_id == current_workspace.id)
        .order_by(KnowledgeBase.id.asc())
    )
    return [_response(item) for item in result.scalars().all()]


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    description = payload.description.strip() if payload.description else None
    if description == "":
        description = None

    knowledge_base = KnowledgeBase(
        workspace_id=current_workspace.id,
        name=name,
        description=description,
        created_by=current_user.id,
    )
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    return _response(knowledge_base)


@router.get("/{knowledge_base_id}/stats")
async def get_knowledge_base_stats(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """知识库统计信息（含文件夹入库状态）。"""
    # 查询该知识库下的收藏夹状态
    folder_rows = await db.execute(
        select(
            FavoriteFolder.id,
            FavoriteFolder.media_id,
            FavoriteFolder.last_sync_at,
            FavoriteFolder.media_count,
        )
        .where(FavoriteFolder.knowledge_base_id == knowledge_base.id)
        .where(FavoriteFolder.last_sync_at.isnot(None))
        .order_by(FavoriteFolder.updated_at.desc())
    )
    folders_data = []
    for row in folder_rows.all():
        fid, media_id, last_sync, media_count = row
        # 统计已入库视频数
        count_result = await db.execute(
            select(func.count(func.distinct(FavoriteVideo.bvid))).where(
                FavoriteVideo.folder_id == fid
            )
        )
        indexed = count_result.scalar() or 0
        folders_data.append(
            {
                "media_id": media_id,
                "indexed_count": indexed,
                "media_count": media_count,
                "last_sync_at": last_sync.isoformat() if last_sync else None,
            }
        )

    # 总视频数
    total_result = await db.execute(
        select(func.count(func.distinct(FavoriteVideo.bvid))).where(
            FavoriteVideo.knowledge_base_id == knowledge_base.id
        )
    )
    total_videos = total_result.scalar() or 0

    return {
        "knowledge_base_id": knowledge_base.id,
        "workspace_id": knowledge_base.workspace_id,
        "total_videos": total_videos,
        "folders": folders_data,
        "scoped": True,
    }


@router.get(
    "/{knowledge_base_id}/scope-options",
    response_model=KnowledgeScopeOptionsResponse,
    response_model_exclude_none=True,
)
async def get_knowledge_scope_options(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeScopeOptionsResponse:
    return await list_scope_options(db, knowledge_base_id=knowledge_base.id)


@router.post("/{knowledge_base_id}/build", response_model=KnowledgeBaseBuildResponse)
async def build_knowledge_base(
    payload: KnowledgeBaseBuildRequest,
    background_tasks: BackgroundTasks,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseBuildResponse:
    binding = await db.get(SourceBinding, payload.source_binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="Source binding not found")

    if not payload.folder_ids:
        raise HTTPException(status_code=400, detail="folder_ids cannot be empty")

    # 获取加密凭据
    cred_result = await db.execute(
        select(SourceCredential)
        .where(SourceCredential.source_binding_id == binding.id)
        .where(SourceCredential.revoked_at.is_(None))
        .order_by(SourceCredential.id.desc())
    )
    credential = cred_result.scalars().first()
    if credential is None:
        raise HTTPException(status_code=400, detail="内容源凭据不存在或已失效")

    try:
        cred_payload = json.loads(decrypt_text(credential.encrypted_payload))
    except Exception:
        raise HTTPException(status_code=500, detail="凭据解密失败")

    task_id = str(uuid.uuid4())
    task = IngestionTask(
        task_id=task_id,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
        created_by=current_user.id,
        status="pending",
        current_step="初始化中...",
    )
    db.add(task)
    await db.commit()

    bili = BilibiliService(
        sessdata=cred_payload.get("SESSDATA"),
        bili_jct=cred_payload.get("bili_jct"),
        dedeuserid=cred_payload.get("DedeUserID"),
    )
    asr_service = ASRService()
    content_fetcher = ContentFetcher(bili, asr_service)
    rag = get_rag_service()
    exclude_bvids = set(payload.exclude_bvids) if payload.exclude_bvids else set()

    background_tasks.add_task(
        _run_scoped_build,
        task_id=task_id,
        bili=bili,
        rag=rag,
        content_fetcher=content_fetcher,
        folder_ids=payload.folder_ids,
        exclude_bvids=exclude_bvids,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
    )

    return KnowledgeBaseBuildResponse(
        task_id=task_id,
        status="pending",
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
    )


async def _run_scoped_build(
    task_id: str,
    bili: BilibiliService,
    rag,
    content_fetcher: ContentFetcher,
    folder_ids: list[int],
    exclude_bvids: set[str],
    workspace_id: int,
    knowledge_base_id: int,
    source_binding_id: int,
):
    """后台执行知识库构建任务，通过 IngestionTask 持久化状态。"""
    from app.database import get_db_context

    async def _update_task(**kwargs):
        async with get_db_context() as s:
            result = await s.execute(
                select(IngestionTask).where(IngestionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                for k, v in kwargs.items():
                    setattr(t, k, v)
                await s.commit()

    try:
        await _update_task(status="running", current_step="同步收藏夹...")

        async with get_db_context() as db:
            total_folders = len(folder_ids)
            for idx, folder_id in enumerate(folder_ids, start=1):
                await _update_task(
                    current_step=f"同步收藏夹 {folder_id} ({idx}/{total_folders})",
                    progress=int((idx - 1) / total_folders * 100),
                )

                await _sync_folder(
                    db=db,
                    bili=bili,
                    rag=rag,
                    content_fetcher=content_fetcher,
                    session_id="",
                    folder_id=folder_id,
                    exclude_bvids=exclude_bvids,
                    workspace_id=workspace_id,
                    knowledge_base_id=knowledge_base_id,
                    source_binding_id=source_binding_id,
                )

        await _update_task(
            status="completed",
            progress=100,
            current_step="完成",
        )
    except Exception as e:
        logger.error(f"构建任务失败 [{task_id}]: {e}")
        await _update_task(status="failed", error_message=str(e), current_step="失败")
    finally:
        await bili.close()


@router.get("/{knowledge_base_id}/build/status/{task_id}")
async def get_build_status(
    task_id: str,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取构建任务状态（按知识库校验）。"""
    result = await db.execute(
        select(IngestionTask).where(IngestionTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.knowledge_base_id != knowledge_base.id:
        raise HTTPException(status_code=404, detail="任务不属于当前知识库")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "total_videos": task.total_items,
        "processed_videos": task.processed_items,
        "message": task.error_message or "",
        "workspace_id": task.workspace_id,
        "knowledge_base_id": task.knowledge_base_id,
    }


@router.post("/{knowledge_base_id}/search", response_model=KnowledgeBaseSearchResponse)
async def search_knowledge_base(
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    bvids = await _resolve_request_scope(
        db,
        knowledge_base_id=knowledge_base.id,
        folder_ids=payload.folder_ids,
        bvids=payload.bvids,
    )
    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        query,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
        bvids=bvids,
    )
    return KnowledgeBaseSearchResponse(
        results=[_search_result(document) for document in documents]
    )


@router.post("/{knowledge_base_id}/chat", response_model=ChatResponse)
async def chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    bvids = await _resolve_request_scope(
        db,
        knowledge_base_id=knowledge_base.id,
        folder_ids=payload.folder_ids,
        bvids=payload.bvids,
    )
    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        question,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
        bvids=bvids,
    )
    return _answer_from_documents(question, documents)


@router.post("/{knowledge_base_id}/chat/stream")
async def stream_chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    response = await chat_with_knowledge_base(
        payload=payload,
        knowledge_base=knowledge_base,
        current_workspace=current_workspace,
        db=db,
    )

    def generate():
        yield response.answer
        if response.thinking:
            yield "\n[[THINKING_JSON]]"
            yield json.dumps(response.thinking, ensure_ascii=False)
        yield "\n[[SOURCES_JSON]]"
        yield json.dumps(response.sources, ensure_ascii=False)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除知识库及其相关数据。"""
    kb_id = knowledge_base.id

    deleted_vectors = 0
    warning: str | None = None
    try:
        rag = get_rag_service()
        deleted_vectors = rag.delete_by_knowledge_base(kb_id)
        logger.info(
            f"已删除知识库 {kb_id}（{knowledge_base.name}）的 {deleted_vectors} 个向量"
        )
    except Exception as exc:
        warning = f"向量清理失败，知识库记录已删除：{exc}"
        logger.warning(f"删除知识库向量失败 [{kb_id}]: {exc}")

    await db.execute(
        IngestionTask.__table__.delete().where(IngestionTask.knowledge_base_id == kb_id)
    )
    await db.execute(
        FavoriteFolder.__table__.delete().where(
            FavoriteFolder.knowledge_base_id == kb_id
        )
    )
    await db.execute(
        FavoriteVideo.__table__.delete().where(FavoriteVideo.knowledge_base_id == kb_id)
    )
    await db.execute(
        VideoCache.__table__.delete().where(VideoCache.knowledge_base_id == kb_id)
    )
    await db.execute(
        VideoTitleOverride.__table__.delete().where(
            VideoTitleOverride.knowledge_base_id == kb_id
        )
    )
    await db.delete(knowledge_base)
    await db.commit()

    result: dict[str, object] = {"ok": True, "deleted_vectors": deleted_vectors}
    if warning:
        result["warning"] = warning
    return result
