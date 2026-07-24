"""User-owned third-party API account schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiAccountCreateRequest(BaseModel):
    provider: str
    display_name: Optional[str] = None
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    protocol: Optional[str] = None
    auth_scheme: Optional[str] = None
    website_url: Optional[str] = None
    notes: Optional[str] = None
    advanced_config: Any = Field(default_factory=dict)
    is_default: bool = False


class ApiAccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    protocol: Optional[str] = None
    auth_scheme: Optional[str] = None
    website_url: Optional[str] = None
    notes: Optional[str] = None
    advanced_config: Any = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class ApiAccountResponse(BaseModel):
    id: int
    provider: str
    provider_label: str
    display_name: str
    base_url: str
    model: str
    thinking_config: dict = Field(default_factory=dict)
    protocol: Optional[str] = None
    auth_scheme: Optional[str] = None
    website_url: Optional[str] = None
    notes: Optional[str] = None
    advanced_config: dict = Field(default_factory=dict)
    enabled: bool
    is_default: bool
    configured: bool = True
    last_validated_at: Optional[datetime] = None
    last_error: Optional[str] = None
