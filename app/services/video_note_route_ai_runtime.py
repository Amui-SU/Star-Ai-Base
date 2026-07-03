"""AI route orchestration for video notes."""

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemUser, Workspace
from app.schemas.video_notes import (
    VideoNoteAiEditRequest,
    VideoNoteAiResponse,
)
from app.services.api_credentials import resolve_user_llm_credentials
from app.services.chat_provider_catalog import _resolve_llm_config
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.video_note_ai import (
    build_ai_edit_messages,
    build_ai_edit_suggestions,
    build_summary_messages,
    build_summary_suggestions,
    generate_video_note_ai_json,
)
from app.services.video_note_presenters import resolve_video_note_source
from app.services.video_note_route_access import get_user_video_note

logger = logging.getLogger(__name__)


async def _generate_ai_payload(
    db: AsyncSession,
    *,
    user: SystemUser,
    messages: list[dict],
) -> tuple[dict | None, str]:
    try:
        credential = await resolve_user_llm_credentials(
            db,
            user,
            global_config_resolver=_resolve_llm_config,
        )
    except HTTPException as exc:
        logger.info(
            "Video note AI skipped because model credentials are missing: %s",
            exc.detail,
        )
        return None, "unavailable"

    try:
        payload = await generate_video_note_ai_json(
            messages,
            credential.to_llm_config(),
            _get_llm_client,
        )
    except Exception as exc:
        logger.warning("Video note AI generation failed, falling back: %s", exc)
        return None, "failed"
    return payload, "generated"


async def generate_video_note_summary_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteAiResponse:
    note = await get_user_video_note(
        db, user=user, workspace=workspace, note_id=note_id
    )
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    ai_payload, ai_status = await _generate_ai_payload(
        db,
        user=user,
        messages=build_summary_messages(note, source),
    )
    return build_summary_suggestions(
        note,
        source,
        ai_payload=ai_payload,
        ai_status=ai_status,
    )


async def edit_video_note_with_ai_from_router(
    db: AsyncSession,
    *,
    note_id: int,
    payload: VideoNoteAiEditRequest,
    user: SystemUser,
    workspace: Workspace,
) -> VideoNoteAiResponse:
    note = await get_user_video_note(
        db, user=user, workspace=workspace, note_id=note_id
    )
    source = await resolve_video_note_source(
        db,
        workspace_id=workspace.id,
        knowledge_base_id=note.knowledge_base_id,
        bvid=note.bvid,
    )
    messages = build_ai_edit_messages(note, payload, source)
    ai_payload = None
    ai_status = "unavailable"
    if messages is not None:
        ai_payload, ai_status = await _generate_ai_payload(
            db,
            user=user,
            messages=messages,
        )
    return build_ai_edit_suggestions(
        note,
        payload,
        source,
        ai_payload=ai_payload,
        ai_status=ai_status,
    )
