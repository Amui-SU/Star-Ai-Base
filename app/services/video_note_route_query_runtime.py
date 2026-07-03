"""Read-side route orchestration for video notes."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, VideoNote, Workspace
from app.schemas.video_notes import VideoNoteDetailResponse, VideoNoteListResponse
from app.services.video_note_presenters import (
    list_item_response,
    list_video_note_sources,
    note_body_matches_query,
    note_matches_query,
    note_to_response,
    resolve_video_note_source,
    video_to_response,
)
from app.services.video_note_route_access import ensure_video_note_knowledge_base


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
    await ensure_video_note_knowledge_base(
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
    await ensure_video_note_knowledge_base(
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
