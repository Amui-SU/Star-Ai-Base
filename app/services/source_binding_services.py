"""Authenticated service factories for source bindings."""

import json
from collections.abc import Callable
from typing import Any

from loguru import logger
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SourceBinding,
    SourceCredential,
    SystemUser,
    Workspace,
)
from app.schemas.source_bindings import LoginStatusResponse, QRCodeResponse
from app.security import decrypt_text, encrypt_text
from app.services.bilibili import BilibiliService, bilibili_service_from_cookies
from app.time_utils import utc_now


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


async def generate_bilibili_binding_qrcode(
    current_user: SystemUser,
    db: AsyncSession,
    *,
    service_class: type[BilibiliService] = BilibiliService,
    set_session: Callable[[str, dict, int], None],
    create_pending_state: Callable[..., Any],
    qrcode_session_ttl: int,
    warning_logger: Callable[[str], None] = logger.warning,
) -> QRCodeResponse:
    bili = service_class()
    try:
        result = await bili.generate_qrcode()
    except Exception as exc:
        warning_logger(f"生成 B站绑定二维码失败: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await bili.close()

    set_session(
        result["qrcode_key"],
        {
            "status": "waiting",
            "purpose": "source_binding",
            "user_id": current_user.id,
        },
        qrcode_session_ttl,
    )
    await create_pending_state(
        db,
        state_key=result["qrcode_key"],
        purpose="source_binding",
        user_id=current_user.id,
        ttl_seconds=qrcode_session_ttl,
    )
    return QRCodeResponse(
        qrcode_key=result["qrcode_key"],
        qrcode_url=result["qrcode_url"],
        qrcode_image_base64=result["qrcode_image_base64"],
    )


async def poll_bilibili_binding_qrcode(
    qrcode_key: str,
    current_user: SystemUser,
    current_workspace: Workspace,
    db: AsyncSession,
    *,
    service_class: type[BilibiliService] = BilibiliService,
    service_from_cookies: Callable[
        [dict[str, Any], type[BilibiliService]], BilibiliService
    ] = bilibili_service_from_cookies,
    get_session: Callable[[str], dict | None],
    login_sessions: dict,
    get_pending_state: Callable[..., Any],
    delete_pending_state: Callable[..., Any],
    encrypt_payload: Callable[[str], str] = encrypt_text,
    warning_logger: Callable[[str], None] = logger.warning,
) -> LoginStatusResponse:
    pending = get_session(qrcode_key)
    pending_is_valid = bool(
        pending
        and pending.get("purpose") == "source_binding"
        and pending.get("user_id") == current_user.id
    )
    if not pending_is_valid:
        pending_record = await get_pending_state(
            db,
            state_key=qrcode_key,
            purpose="source_binding",
            user_id=current_user.id,
        )
        pending_is_valid = pending_record is not None
    if not pending_is_valid:
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")

    bili = service_class()
    try:
        result = await bili.poll_qrcode_status(qrcode_key)
    except Exception as exc:
        warning_logger(f"轮询 B站绑定二维码失败: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await bili.close()

    response = LoginStatusResponse(
        status=result["status"],
        message=result["message"],
    )
    if result["status"] != "confirmed":
        return response

    cookies = result.get("cookies", {})
    bili_auth = service_from_cookies(cookies, service_class)
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
        last_verified_at=utc_now(),
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
            encrypted_payload=encrypt_payload(
                json.dumps(credential_payload, ensure_ascii=False)
            ),
        )
    )
    await db.commit()

    login_sessions.pop(qrcode_key, None)
    await delete_pending_state(db, qrcode_key)
    response_mid = int(external_id) if external_id.isdigit() else external_id
    response.user_info = {
        "mid": response_mid,
        "uname": binding.external_account_name,
        "face": binding.external_avatar_url,
    }
    response.session_id = str(binding.id)
    return response
