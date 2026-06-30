"""Request preparation for knowledge-base build jobs."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgeBase,
    SourceBinding,
    SourceCredential,
    SystemUser,
    Workspace,
)
from app.schemas.knowledge_base import (
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
)
from app.security import decrypt_text
from app.services.bilibili import bilibili_service_from_cookies
from app.services.ingestion_tasks import create_ingestion_task
from app.services.knowledge_base_presenters import dedupe_ints, dedupe_strings


@dataclass(frozen=True)
class KnowledgeBaseBuildPlan:
    response: KnowledgeBaseBuildResponse
    task_kwargs: dict[str, Any]


async def prepare_knowledge_base_build_request(
    db: AsyncSession,
    *,
    payload: KnowledgeBaseBuildRequest,
    user: SystemUser,
    workspace: Workspace,
    knowledge_base: KnowledgeBase,
    bilibili_service_class: type,
    asr_service_factory: Callable[[], Any],
    content_fetcher_class: type,
    rag_service_factory: Callable[[], Any],
) -> KnowledgeBaseBuildPlan:
    binding = await db.get(SourceBinding, payload.source_binding_id)
    if (
        binding is None
        or binding.user_id != user.id
        or binding.workspace_id != workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="Source binding not found")

    folder_ids = dedupe_ints(payload.folder_ids)
    video_folder_ids = dedupe_ints(payload.video_folder_ids)
    include_bvids = set(dedupe_strings(payload.bvids))

    if not folder_ids and not (video_folder_ids and include_bvids):
        raise HTTPException(status_code=400, detail="folder_ids cannot be empty")

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

    task_id = await create_ingestion_task(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base.id,
        source_binding_id=binding.id,
        user_id=user.id,
        current_step="初始化中...",
    )

    bili = bilibili_service_from_cookies(cred_payload, bilibili_service_class)
    asr_service = asr_service_factory()
    content_fetcher = content_fetcher_class(bili, asr_service)
    rag = rag_service_factory()
    exclude_bvids = set(payload.exclude_bvids) if payload.exclude_bvids else set()

    return KnowledgeBaseBuildPlan(
        response=KnowledgeBaseBuildResponse(
            task_id=task_id,
            status="pending",
            workspace_id=workspace.id,
            knowledge_base_id=knowledge_base.id,
            source_binding_id=binding.id,
        ),
        task_kwargs={
            "task_id": task_id,
            "bili": bili,
            "rag": rag,
            "content_fetcher": content_fetcher,
            "folder_ids": folder_ids,
            "video_folder_ids": video_folder_ids,
            "include_bvids": include_bvids,
            "exclude_bvids": exclude_bvids,
            "workspace_id": workspace.id,
            "knowledge_base_id": knowledge_base.id,
            "source_binding_id": binding.id,
        },
    )
