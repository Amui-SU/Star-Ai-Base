"""Video note API schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

VideoNoteTemplateId = Literal["standard", "blank"]


class VideoNoteBlock(BaseModel):
    id: str
    type: str
    text: str | None = None
    level: int | None = None
    items: list[Any] | None = None
    checked: bool | None = None
    source: str | None = None


class VideoNotePart(BaseModel):
    page: int
    cid: int
    part: str
    duration: int


class VideoNoteVideoResponse(BaseModel):
    bvid: str
    title: str
    original_title: str | None = None
    display_title: str | None = None
    folder_title: str | None = None
    owner_name: str | None = None
    duration: int | None = None
    pic_url: str | None = None
    url: str
    parts: list[VideoNotePart] | None = None


class VideoNoteResponse(BaseModel):
    id: int
    user_id: int
    workspace_id: int
    knowledge_base_id: int
    bvid: str
    source_binding_id: int | None = None
    title: str
    template_id: str
    blocks: list[dict]
    tags: list[str]
    summary_status: str
    summary_generated_at: datetime | None = None
    export_filename_template: str | None = None
    created_at: datetime
    updated_at: datetime
    video: VideoNoteVideoResponse | None = None


class VideoNoteDetailResponse(BaseModel):
    note: VideoNoteResponse | None = None
    video: VideoNoteVideoResponse
    can_create: bool


class VideoNoteListItemResponse(BaseModel):
    bvid: str
    title: str
    display_title: str | None = None
    folder_title: str | None = None
    note_id: int | None = None
    has_note: bool
    last_edited_at: datetime | None = None
    summary_status: str
    tags: list[str] = Field(default_factory=list)


class VideoNoteListResponse(BaseModel):
    knowledge_base_id: int
    items: list[VideoNoteListItemResponse]


class VideoNoteCreateRequest(BaseModel):
    knowledge_base_id: int
    bvid: str
    template_id: VideoNoteTemplateId = "standard"

    @field_validator("bvid")
    @classmethod
    def normalize_bvid(cls, value: str) -> str:
        bvid = (value or "").strip()
        if not bvid:
            raise ValueError("bvid cannot be empty")
        return bvid


class VideoNoteSaveRequest(BaseModel):
    title: str | None = None
    blocks: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    export_filename_template: str | None = None


class VideoNoteExportResponse(BaseModel):
    markdown: str
    filename: str


class VideoNoteAiEditRequest(BaseModel):
    action: str
    instruction: str | None = None
    selected_block_ids: list[str] = Field(default_factory=list)


class VideoNoteAiOperation(BaseModel):
    kind: str
    block: dict | None = None
    target_block_id: str | None = None
    blocks: list[dict] | None = None


class VideoNoteAiResponse(BaseModel):
    operations: list[VideoNoteAiOperation]
    tag_suggestions: list[str] = Field(default_factory=list)
    message: str
