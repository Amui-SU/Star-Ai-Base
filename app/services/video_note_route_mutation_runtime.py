"""Write-side route orchestration for video notes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, VideoNote, Workspace
from app.schemas.video_notes import (
    VideoNoteCreateRequest,
    VideoNoteResponse,
    VideoNoteSaveRequest,
)
from app.services.video_note_presenters import (
    build_standard_note_blocks,
    note_to_response,
    resolve_video_note_source,
)
from app.services.video_note_route_access import (
    ensure_video_note_knowledge_base,
    get_user_video_note,
    normalize_video_note_tags,
)
from app.time_utils import utc_now


async def create_video_note_from_router(
    db: AsyncSession,
    *,
    payload: VideoNoteCreateRequest,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteResponse:
    await ensure_video_note_knowledge_base(
        db,
        workspace=workspace,
        knowledge_base_id=payload.knowledge_base_id,
    )
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=payload.knowledge_base_id,
        bvid=payload.bvid,
    )
    existing = await db.execute(
        select(VideoNote).where(
            VideoNote.user_id == user.id,
            VideoNote.workspace_id == workspace.id,
            VideoNote.knowledge_base_id == payload.knowledge_base_id,
            VideoNote.bvid == payload.bvid,
        )
    )
    note = existing.scalar_one_or_none()
    if note is not None:
        return VideoNoteResponse(**note_to_response(note, source))

    blocks = (
        build_standard_note_blocks(source) if payload.template_id == "standard" else []
    )
    note = VideoNote(
        user_id=user.id,
        workspace_id=workspace.id,
        knowledge_base_id=payload.knowledge_base_id,
        bvid=payload.bvid,
        source_binding_id=source.source_binding_id,
        title=source.title,
        template_id=payload.template_id,
        blocks_json=blocks,
        tags_json=[],
        summary_status=(
            "seeded"
            if payload.template_id == "standard" and (source.content or source.outline)
            else "not_generated"
        ),
        export_filename_template="{{title}} - {{bvid}}.md",
    )
    db.add(note)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Video note already exists"
        ) from exc
    await db.refresh(note)
    return VideoNoteResponse(**note_to_response(note, source))


async def update_video_note_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    payload: VideoNoteSaveRequest,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteResponse:
    note = await get_user_video_note(
        db, user=user, workspace=workspace, note_id=note_id
    )
    await ensure_video_note_knowledge_base(
        db,
        workspace=workspace,
        knowledge_base_id=note.knowledge_base_id,
    )
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    if payload.title is not None and payload.title.strip():
        note.title = payload.title.strip()
    note.blocks_json = payload.blocks
    note.tags_json = normalize_video_note_tags(payload.tags)
    note.export_filename_template = payload.export_filename_template
    note.updated_at = utc_now()
    await db.commit()
    await db.refresh(note)
    return VideoNoteResponse(**note_to_response(note, source))
