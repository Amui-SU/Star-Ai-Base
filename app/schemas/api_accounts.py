"""User-owned third-party API account schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApiAccountCreateRequest(BaseModel):
    provider: str
    display_name: Optional[str] = None
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    is_default: bool = False


class ApiAccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_config: Optional[dict] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class ApiAccountResponse(BaseModel):
    id: int
    provider: str
    provider_label: str
    display_name: str
    base_url: str
    model: str
    thinking_config: dict = {}
    enabled: bool
    is_default: bool
    configured: bool = True
    last_validated_at: Optional[datetime] = None
    last_error: Optional[str] = None
