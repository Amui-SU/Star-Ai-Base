import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_workspace
from app.models import (
    LoginStatusResponse,
    QRCodeResponse,
    SourceBinding,
    SourceBindingResponse,
    SourceCredential,
    SystemUser,
    Workspace,
)
from app.routers.auth import login_sessions
from app.security import encrypt_text
from app.services.bilibili import BilibiliService

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


@router.get("/bilibili/qrcode", response_model=QRCodeResponse)
async def generate_bilibili_binding_qrcode(
    current_user: SystemUser = Depends(get_current_user),
) -> QRCodeResponse:
    bili = BilibiliService()
    try:
        result = await bili.generate_qrcode()
    finally:
        await bili.close()

    login_sessions[result["qrcode_key"]] = {
        "status": "waiting",
        "purpose": "source_binding",
        "user_id": current_user.id,
    }
    return QRCodeResponse(
        qrcode_key=result["qrcode_key"],
        qrcode_url=result["qrcode_url"],
        qrcode_image_base64=result["qrcode_image_base64"],
    )


@router.get("/bilibili/qrcode/poll/{qrcode_key}", response_model=LoginStatusResponse)
async def poll_bilibili_binding_qrcode(
    qrcode_key: str,
    current_user: SystemUser = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> LoginStatusResponse:
    pending = login_sessions.get(qrcode_key)
    if (
        not pending
        or pending.get("purpose") != "source_binding"
        or pending.get("user_id") != current_user.id
    ):
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")

    bili = BilibiliService()
    try:
        result = await bili.poll_qrcode_status(qrcode_key)
    finally:
        await bili.close()

    response = LoginStatusResponse(
        status=result["status"],
        message=result["message"],
    )
    if result["status"] != "confirmed":
        return response

    cookies = result.get("cookies", {})
    bili_auth = BilibiliService(
        sessdata=cookies.get("SESSDATA"),
        bili_jct=cookies.get("bili_jct"),
        dedeuserid=cookies.get("DedeUserID"),
    )
    try:
        user_info = await bili_auth.get_user_info()
    finally:
        await bili_auth.close()

    external_id = str(user_info.get("mid") or cookies.get("DedeUserID") or "")
    if not external_id:
        raise HTTPException(status_code=502, detail="B 站账号信息缺少用户 ID")

    binding = SourceBinding(
        user_id=current_user.id,
        workspace_id=current_workspace.id,
        source_type="bilibili",
        external_account_id=external_id,
        external_account_name=user_info.get("uname"),
        external_avatar_url=user_info.get("face"),
        status="active",
        last_verified_at=datetime.utcnow(),
    )
    db.add(binding)
    await db.flush()

    credential_payload = {
        "SESSDATA": cookies.get("SESSDATA"),
        "bili_jct": cookies.get("bili_jct"),
        "DedeUserID": cookies.get("DedeUserID"),
    }
    db.add(
        SourceCredential(
            user_id=current_user.id,
            source_binding_id=binding.id,
            encrypted_payload=encrypt_text(
                json.dumps(credential_payload, ensure_ascii=False)
            ),
        )
    )
    await db.commit()

    login_sessions.pop(qrcode_key, None)
    response_mid = int(external_id) if external_id.isdigit() else external_id
    response.user_info = {
        "mid": response_mid,
        "uname": binding.external_account_name,
        "face": binding.external_avatar_url,
    }
    response.session_id = str(binding.id)
    return response
