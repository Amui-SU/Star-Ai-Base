"""Knowledge-base API schemas."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: Optional[str] = None


class KnowledgeBaseSearchRequest(BaseModel):
    query: str
    k: int = 5
    folder_ids: Optional[list[int]] = None
    bvids: Optional[list[str]] = None


class KnowledgeBaseSearchResult(BaseModel):
    content: str
    bvid: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None


class KnowledgeBaseSearchResponse(BaseModel):
    results: list[KnowledgeBaseSearchResult]


class KnowledgeBaseChatRequest(BaseModel):
    question: str
    k: int = 5
    folder_ids: Optional[list[int]] = None
    bvids: Optional[list[str]] = None
    web_search: bool = False
    web_search_provider: str = "auto"

    @field_validator("web_search_provider")
    @classmethod
    def normalize_web_search_provider(cls, value: str) -> str:
        provider = (value or "auto").strip().lower()
        if provider not in {"auto", "tavily", "html"}:
            raise ValueError("unsupported web search provider")
        return provider


class KnowledgeScopeVideo(BaseModel):
    bvid: str
    title: str
    original_title: Optional[str] = None
    custom_title: Optional[str] = None
    display_title: Optional[str] = None


class KnowledgeScopeFolder(BaseModel):
    media_id: int
    title: str
    video_count: int
    videos: list[KnowledgeScopeVideo]


class KnowledgeScopeOptionsResponse(BaseModel):
    folders: list[KnowledgeScopeFolder]


class KnowledgeBaseBuildRequest(BaseModel):
    source_binding_id: int
    folder_ids: list[int] = Field(default_factory=list)
    video_folder_ids: Optional[list[int]] = None
    bvids: Optional[list[str]] = None
    exclude_bvids: Optional[list[str]] = None


class KnowledgeBaseBuildResponse(BaseModel):
    task_id: str
    status: str
    workspace_id: int
    knowledge_base_id: int
    source_binding_id: int
