from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_workspace,
    get_knowledge_base_for_user,
)
from app.models import (
    KnowledgeBase,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
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
