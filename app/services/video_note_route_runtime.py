"""Route orchestration for video note endpoints."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, SystemUser, VideoNote, Workspace
from app.schemas.video_notes import (
    VideoNoteAiEditRequest,
    VideoNoteAiResponse,
    VideoNoteCreateRequest,
    VideoNoteDetailResponse,
    VideoNoteExportResponse,
    VideoNoteListResponse,
    VideoNoteResponse,
    VideoNoteSaveRequest,
)
from app.services.video_note_ai import (
    build_ai_edit_suggestions,
    build_summary_suggestions,
)
from app.services.video_note_markdown import (
    render_video_note_filename,
    render_video_note_markdown,
)
from app.services.video_note_presenters import (
    build_standard_note_blocks,
    list_item_response,
    list_video_note_sources,
    note_body_matches_query,
    note_matches_query,
    note_to_response,
    resolve_video_note_source,
    video_to_response,
)
from app.time_utils import utc_now


async def _ensure_knowledge_base(
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


async def _get_user_note(
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


def _normalized_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags:
        value = str(tag).strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            normalized.append(value)
    return normalized


async def list_video_notes_from_router(
    db: AsyncSession,
    *,
    user: SystemUser,
    workspace: Workspace,
    knowledge_base_id: int,
    q: str | None,
    tag: str | None,
    include_body_search: bool,
) -> VideoNoteListResponse:
    await _ensure_knowledge_base(
        db,
        workspace=workspace,
        knowledge_base_id=knowledge_base_id,
    )
    rows = await list_video_note_sources(
        db,
        user_id=user.id,
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base_id,
    )

    items = []
    query = (q or "").strip()
    tag_filter = (tag or "").strip().lower()
    for source, note in rows:
        if tag_filter and tag_filter not in {
            str(item).lower() for item in (note.tags_json if note else [])
        }:
            continue
        if query and not note_matches_query(note, source, query):
            if not include_body_search or not note_body_matches_query(note, query):
                continue
        items.append(list_item_response(source, note))
    return VideoNoteListResponse(knowledge_base_id=knowledge_base_id, items=items)


async def get_video_note_detail_from_router(
    db: AsyncSession,
    *,
    user: SystemUser,
    workspace: Workspace,
    knowledge_base_id: int,
    bvid: str,
) -> VideoNoteDetailResponse:
    await _ensure_knowledge_base(
        db,
        workspace=workspace,
        knowledge_base_id=knowledge_base_id,
    )
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base_id,
        bvid=bvid,
    )
    result = await db.execute(
        select(VideoNote).where(
            VideoNote.user_id == user.id,
            VideoNote.workspace_id == workspace.id,
            VideoNote.knowledge_base_id == knowledge_base_id,
            VideoNote.bvid == bvid,
        )
    )
    note = result.scalar_one_or_none()
    return VideoNoteDetailResponse(
        note=note_to_response(note, source) if note else None,
        video=video_to_response(source),
        can_create=note is None,
    )


async def create_video_note_from_router(
    db: AsyncSession,
    *,
    payload: VideoNoteCreateRequest,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteResponse:
    await _ensure_knowledge_base(
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
    note = await _get_user_note(db, user=user, workspace=workspace, note_id=note_id)
    await _ensure_knowledge_base(
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
    note.tags_json = _normalized_tags(payload.tags)
    note.export_filename_template = payload.export_filename_template
    note.updated_at = utc_now()
    await db.commit()
    await db.refresh(note)
    return VideoNoteResponse(**note_to_response(note, source))


async def export_video_note_markdown_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteExportResponse:
    note = await _get_user_note(db, user=user, workspace=workspace, note_id=note_id)
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    return VideoNoteExportResponse(
        markdown=render_video_note_markdown(note, source),
        filename=render_video_note_filename(note, source),
    )


async def generate_video_note_summary_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteAiResponse:
    note = await _get_user_note(db, user=user, workspace=workspace, note_id=note_id)
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    return build_summary_suggestions(note, source)


async def edit_video_note_with_ai_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    payload: VideoNoteAiEditRequest,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteAiResponse:
    note = await _get_user_note(db, user=user, workspace=workspace, note_id=note_id)
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    return build_ai_edit_suggestions(note, payload, source)
