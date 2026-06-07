from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_workspace
from app.models import SourceBinding, SourceBindingResponse, SystemUser, Workspace

router = APIRouter(prefix="/source-bindings", tags=["source-bindings"])


def _response(binding: SourceBinding) -> SourceBindingResponse:
    return SourceBindingResponse(
        id=binding.id,
        source_type=binding.source_type,
        external_account_id=binding.external_account_id,
        external_account_name=binding.external_account_name,
        external_avatar_url=binding.external_avatar_url,
        status=binding.status,
    )


@router.get("", response_model=list[SourceBindingResponse])
async def list_bindings(
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> list[SourceBindingResponse]:
    result = await db.execute(
        select(SourceBinding)
        .where(SourceBinding.user_id == current_user.id)
        .where(SourceBinding.workspace_id == current_workspace.id)
        .order_by(SourceBinding.id.desc())
    )
    return [_response(binding) for binding in result.scalars().all()]


@router.delete("/{binding_id}")
async def revoke_binding(
    binding_id: int,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    binding = await db.get(SourceBinding, binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
    ):
        raise HTTPException(status_code=404, detail="内容源绑定不存在")

    binding.status = "revoked"
    await db.commit()
    return {"ok": True}
