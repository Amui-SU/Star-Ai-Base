from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
)
from app.models import (
    ChatResponse,
    KnowledgeBase,
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    SourceBinding,
    SystemUser,
    Workspace,
)
from app.routers.knowledge import get_rag_service

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
) -> dict:
    return {
        "knowledge_base_id": knowledge_base.id,
        "workspace_id": knowledge_base.workspace_id,
        "scoped": True,
    }


@router.post("/{knowledge_base_id}/build", response_model=KnowledgeBaseBuildResponse)
async def build_knowledge_base(
    payload: KnowledgeBaseBuildRequest,
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

    return KnowledgeBaseBuildResponse(
        task_id=str(uuid.uuid4()),
        status="pending",
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
    )


@router.post("/{knowledge_base_id}/search", response_model=KnowledgeBaseSearchResponse)
async def search_knowledge_base(
    payload: KnowledgeBaseSearchRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> KnowledgeBaseSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        query,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
    )
    return KnowledgeBaseSearchResponse(
        results=[_search_result(document) for document in documents]
    )


@router.post("/{knowledge_base_id}/chat", response_model=ChatResponse)
async def chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    k = max(1, min(payload.k, 20))
    rag = get_rag_service()
    documents = rag.search_in_knowledge_base(
        question,
        workspace_id=current_workspace.id,
        knowledge_base_id=knowledge_base.id,
        k=k,
    )
    return _answer_from_documents(question, documents)


@router.post("/{knowledge_base_id}/chat/stream")
async def stream_chat_with_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    knowledge_base: KnowledgeBase = Depends(get_knowledge_base_for_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    response = await chat_with_knowledge_base(
        payload=payload,
        knowledge_base=knowledge_base,
        current_workspace=current_workspace,
    )

    def generate():
        yield response.answer
        if response.thinking:
            yield "\n[[THINKING_JSON]]"
            yield json.dumps(response.thinking, ensure_ascii=False)
        yield "\n[[SOURCES_JSON]]"
        yield json.dumps(response.sources, ensure_ascii=False)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
