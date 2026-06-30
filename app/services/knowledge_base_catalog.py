"""Catalog commands for workspace knowledge bases."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgeBase,
    SystemUser,
    Workspace,
)
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseResponse
from app.services.knowledge_base_presenters import response_from_knowledge_base


async def list_workspace_knowledge_bases(
    db: AsyncSession,
    *,
    workspace: Workspace,
) -> list[KnowledgeBaseResponse]:
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.workspace_id == workspace.id)
        .order_by(KnowledgeBase.id.asc())
    )
    return [response_from_knowledge_base(item) for item in result.scalars().all()]


async def create_workspace_knowledge_base(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseCreateRequest,
    user: SystemUser,
    workspace: Workspace,
) -> KnowledgeBaseResponse:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    description = payload.description.strip() if payload.description else None
    if description == "":
        description = None

    knowledge_base = KnowledgeBase(
        workspace_id=workspace.id,
        name=name,
        description=description,
        created_by=user.id,
    )
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    return response_from_knowledge_base(knowledge_base)
