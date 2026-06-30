"""Authentication and user-management API schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SystemRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    code: str


class SystemLoginRequest(BaseModel):
    email: str
    password: str


class SystemDisplayNameUpdateRequest(BaseModel):
    display_name: str


class SystemUserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    status: str = "active"
    is_admin: bool = False


class AdminUserResponse(SystemUserResponse):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]


class AdminUserStatusUpdateRequest(BaseModel):
    status: str


class AdminPasswordResetResponse(BaseModel):
    user: AdminUserResponse
    temporary_password: str


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    role: str


class SystemAuthResponse(BaseModel):
    user: SystemUserResponse
    workspace: WorkspaceResponse
    session_token: Optional[str] = None
