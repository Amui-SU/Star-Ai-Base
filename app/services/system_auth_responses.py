"""Response builders for system authentication."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SystemUser,
    SystemUserResponse,
    Workspace,
    WorkspaceMember,
    WorkspaceResponse,
)
from app.services.system_auth_admin import is_admin_user


async def user_response(db: AsyncSession, user: SystemUser) -> SystemUserResponse:
    return SystemUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        is_admin=await is_admin_user(db, user),
    )


def workspace_response(
    workspace: Workspace, member: WorkspaceMember
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=member.role,
    )
