"""Export route orchestration for video notes."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.schemas.video_notes import VideoNoteExportResponse
from app.services.video_note_markdown import (
    render_video_note_filename,
    render_video_note_markdown,
)
from app.services.video_note_presenters import resolve_video_note_source
from app.services.video_note_route_access import get_user_video_note


async def export_video_note_markdown_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteExportResponse:
    note = await get_user_video_note(
        db, user=user, workspace=workspace, note_id=note_id
    )
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
