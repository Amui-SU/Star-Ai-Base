"""Authenticated service factories for source bindings."""

import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceBinding, SourceCredential, SystemUser, Workspace
from app.security import decrypt_text
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies


async def get_bilibili_service_for_binding(
    binding_id: int,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    service_class: type[BilibiliService] = BilibiliService,
    service_from_cookies: Callable[
        [dict[str, Any], type[BilibiliService]], BilibiliService
    ] = (bilibili_service_from_cookies),
    decrypt_payload: Callable[[str], str] = decrypt_text,
) -> BilibiliService:
    """Resolve a source binding into an authenticated Bilibili service."""
    binding = await db.get(SourceBinding, binding_id)
    if (
        binding is None
        or binding.user_id != current_user.id
        or binding.workspace_id != current_workspace.id
        or binding.status != "active"
    ):
        raise HTTPException(status_code=404, detail="内容源绑定不存在或已失效")

    cred_result = await db.execute(
        select(SourceCredential)
        .where(SourceCredential.source_binding_id == binding_id)
        .where(SourceCredential.revoked_at.is_(None))
        .order_by(SourceCredential.id.desc())
    )
    credential = cred_result.scalars().first()
    if credential is None:
        raise HTTPException(status_code=400, detail="内容源凭据不存在或已失效")

    try:
        payload = json.loads(decrypt_payload(credential.encrypted_payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="凭据解密失败") from exc

    return service_from_cookies(payload, service_class)
