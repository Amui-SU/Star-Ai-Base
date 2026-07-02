"""Video note API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_workspace
from app.models import SystemUser, Workspace
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
from app.services.video_note_route_runtime import (
    create_video_note_from_router,
    edit_video_note_with_ai_from_router,
    export_video_note_markdown_from_router,
    generate_video_note_summary_from_router,
    get_video_note_detail_from_router,
    list_video_notes_from_router,
    update_video_note_from_router,
)

router = APIRouter(prefix="/video-notes", tags=["video-notes"])


@router.get("", response_model=VideoNoteListResponse)
async def list_video_notes(
    knowledge_base_id: int,
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    include_body_search: bool = Query(default=False),
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteListResponse:
    return await list_video_notes_from_router(
        db,
        user=current_user,
        workspace=current_workspace,
        knowledge_base_id=knowledge_base_id,
        q=q,
        tag=tag,
        include_body_search=include_body_search,
    )


@router.get("/{knowledge_base_id}/{bvid}", response_model=VideoNoteDetailResponse)
async def get_video_note_detail(
    knowledge_base_id: int,
    bvid: str,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteDetailResponse:
    return await get_video_note_detail_from_router(
        db,
        user=current_user,
        workspace=current_workspace,
        knowledge_base_id=knowledge_base_id,
        bvid=bvid,
    )


@router.post("", response_model=VideoNoteResponse)
async def create_video_note(
    payload: VideoNoteCreateRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteResponse:
    return await create_video_note_from_router(
        db,
        payload=payload,
        user=current_user,
        workspace=current_workspace,
    )


@router.put("/{note_id}", response_model=VideoNoteResponse)
async def update_video_note(
    note_id: int,
    payload: VideoNoteSaveRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteResponse:
    return await update_video_note_from_router(
        db,
        note_id=note_id,
        payload=payload,
        user=current_user,
        workspace=current_workspace,
    )


@router.post("/{note_id}/export/markdown", response_model=VideoNoteExportResponse)
async def export_video_note_markdown(
    note_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteExportResponse:
    return await export_video_note_markdown_from_router(
        db,
        note_id=note_id,
        user=current_user,
        workspace=current_workspace,
    )


@router.post("/{note_id}/generate-summary", response_model=VideoNoteAiResponse)
async def generate_video_note_summary(
    note_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteAiResponse:
    return await generate_video_note_summary_from_router(
        db,
        note_id=note_id,
        user=current_user,
        workspace=current_workspace,
    )


@router.post("/{note_id}/ai-edit", response_model=VideoNoteAiResponse)
async def edit_video_note_with_ai(
    note_id: int,
    payload: VideoNoteAiEditRequest,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> VideoNoteAiResponse:
    return await edit_video_note_with_ai_from_router(
        db,
        note_id=note_id,
        payload=payload,
        user=current_user,
        workspace=current_workspace,
    )
