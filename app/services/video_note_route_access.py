"""Shared data access helpers for video note route runtimes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, SystemUser, VideoNote, Workspace


async def ensure_video_note_knowledge_base(
    db: AsyncSession,
    *,
    workspace: Workspace,
    knowledge_base_id: int,
) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.workspace_id == workspace.id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return knowledge_base


async def get_user_video_note(
    db: AsyncSession,
    *,
    user: SystemUser,
    workspace: Workspace,
    note_id: int,
) -> VideoNote:
    result = await db.execute(
        select(VideoNote).where(
            VideoNote.id == note_id,
            VideoNote.user_id == user.id,
            VideoNote.workspace_id == workspace.id,
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Video note not found")
    return note


def normalize_video_note_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags:
        value = str(tag).strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            normalized.append(value)
    return normalized
