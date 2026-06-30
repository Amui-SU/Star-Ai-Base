"""Chat API schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Chat request."""

    question: str
    session_id: Optional[str] = None
    folder_ids: Optional[list[int]] = None


class ChatResponse(BaseModel):
    """Chat response."""

    answer: str
    sources: list[dict]
    thinking: Optional[str] = None
    web_search: Optional[dict] = None


class ChatHistoryMessageRequest(BaseModel):
    role: str
    content: str
    thinking: Optional[str] = None
    sources: Optional[list[dict]] = None
    web_search: Optional[dict] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = (value or "").strip().lower()
        if role not in {"user", "assistant"}:
            raise ValueError("unsupported message role")
        return role


class ChatConversationSaveRequest(BaseModel):
    title: Optional[str] = None
    workspace_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    scope: Optional[dict] = None
    web_search: bool = False
    web_search_provider: str = "auto"
    messages: list[ChatHistoryMessageRequest] = Field(default_factory=list)

    @field_validator("web_search_provider")
    @classmethod
    def normalize_history_web_search_provider(cls, value: str) -> str:
        provider = (value or "auto").strip().lower()
        if provider not in {"auto", "tavily", "html"}:
            raise ValueError("unsupported web search provider")
        return provider


class ChatHistoryMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    thinking: Optional[str] = None
    sources: Optional[list[dict]] = None
    web_search: Optional[dict] = None
    sequence: int
    created_at: datetime


class ChatConversationSummaryResponse(BaseModel):
    id: int
    user_id: int
    workspace_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    title: str
    scope: Optional[dict] = None
    web_search: bool
    web_search_provider: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatConversationResponse(ChatConversationSummaryResponse):
    messages: list[ChatHistoryMessageResponse]


class ChatConversationListResponse(BaseModel):
    items: list[ChatConversationSummaryResponse]
