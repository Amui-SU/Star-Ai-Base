"""
Bilibili RAG 知识库系统

认证路由 - 处理 B站登录
"""

import time
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from app.database import get_db, get_db_context
from app.models import (
    OAuthPendingState,
    QRCodeResponse,
    LoginStatusResponse,
    UserSession as UserSessionModel,
)
from app.services.bilibili import (
    BilibiliService,
    bilibili_service_from_cookies,
    normalize_bilibili_cookies,
)
from app.security import decrypt_text, encrypt_text
from app.time_utils import utc_now_naive
import uuid

router = APIRouter(prefix="/auth", tags=["认证"])

# 旧登录热缓存；二维码 pending state 以数据库为准。
login_sessions: dict = {}

# 会话过期时间（秒）
QRCODE_SESSION_TTL = 300  # 二维码 5 分钟过期
LOGIN_SESSION_TTL = 14 * 86400  # 登录会话 14 天过期
ENCRYPTED_COOKIE_PREFIX = "fernet:"
LEGACY_QRCODE_PENDING_PURPOSE = "legacy_auth_qrcode"


def _encrypt_session_cookie(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    return f"{ENCRYPTED_COOKIE_PREFIX}{encrypt_text(value)}"


def _decrypt_session_cookie(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    if not value.startswith(ENCRYPTED_COOKIE_PREFIX):
        return value
    return decrypt_text(value.removeprefix(ENCRYPTED_COOKIE_PREFIX))


def _cookies_from_db_session(db_session: UserSessionModel) -> dict:
    return {
        "SESSDATA": _decrypt_session_cookie(db_session.sessdata),
        "bili_jct": _decrypt_session_cookie(db_session.bili_jct),
        "DedeUserID": db_session.dedeuserid,
    }


def _cleanup_expired_sessions():
    """清理过期会话（在每次访问时触发）"""
    now = time.time()
    expired_keys = [
        key
        for key, val in login_sessions.items()
        if now - val.get("_created_at", 0) > val.get("_ttl", QRCODE_SESSION_TTL)
    ]
    for key in expired_keys:
        login_sessions.pop(key, None)


def _set_session(key: str, value: dict, ttl: int = LOGIN_SESSION_TTL):
    """写入会话并附加创建时间和 TTL"""
    value["_created_at"] = time.time()
    value["_ttl"] = ttl
    login_sessions[key] = value


def _get_session(key: str) -> dict | None:
    """读取会话（自动清理过期）"""
    _cleanup_expired_sessions()
    session = login_sessions.get(key)
    if session is None:
        return None
    now = time.time()
    if now - session.get("_created_at", 0) > session.get("_ttl", LOGIN_SESSION_TTL):
        login_sessions.pop(key, None)
        return None
    return session


async def _create_legacy_qrcode_pending_state(
    db: AsyncSession, qrcode_key: str
) -> None:
    now = utc_now_naive()
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.expires_at < now)
    )
    result = await db.execute(
        select(OAuthPendingState).where(OAuthPendingState.state_key == qrcode_key)
    )
    pending = result.scalar_one_or_none()
    expires_at = now + timedelta(seconds=QRCODE_SESSION_TTL)
    if pending is None:
        db.add(
            OAuthPendingState(
                state_key=qrcode_key,
                purpose=LEGACY_QRCODE_PENDING_PURPOSE,
                expires_at=expires_at,
            )
        )
    else:
        pending.purpose = LEGACY_QRCODE_PENDING_PURPOSE
        pending.user_id = None
        pending.workspace_id = None
        pending.expires_at = expires_at
    await db.commit()


async def _has_legacy_qrcode_pending_state(db: AsyncSession, qrcode_key: str) -> bool:
    now = utc_now_naive()
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.expires_at < now)
    )
    result = await db.execute(
        select(OAuthPendingState).where(OAuthPendingState.state_key == qrcode_key)
    )
    pending = result.scalar_one_or_none()
    await db.commit()
    return bool(
        pending
        and pending.purpose == LEGACY_QRCODE_PENDING_PURPOSE
        and pending.expires_at > now
    )


async def _delete_legacy_qrcode_pending_state(
    db: AsyncSession, qrcode_key: str
) -> None:
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.state_key == qrcode_key)
    )
    await db.commit()


@router.get("/qrcode", response_model=QRCodeResponse)
async def generate_qrcode(db: AsyncSession = Depends(get_db)):
    """
    生成登录二维码

    返回二维码 key 和 base64 编码的二维码图片
    """
    try:
        bili = BilibiliService()
        try:
            result = await bili.generate_qrcode()
        finally:
            await bili.close()

        # 存储会话
        _set_session(
            result["qrcode_key"],
            {"status": "waiting", "purpose": LEGACY_QRCODE_PENDING_PURPOSE},
            QRCODE_SESSION_TTL,
        )
        await _create_legacy_qrcode_pending_state(db, result["qrcode_key"])

        return QRCodeResponse(
            qrcode_key=result["qrcode_key"],
            qrcode_url=result["qrcode_url"],
            qrcode_image_base64=result["qrcode_image_base64"],
        )

    except Exception as e:
        logger.error(f"生成二维码失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成二维码失败: {str(e)}")


@router.get("/qrcode/poll/{qrcode_key}", response_model=LoginStatusResponse)
async def poll_qrcode_status(qrcode_key: str, db: AsyncSession = Depends(get_db)):
    """
    轮询二维码登录状态
    """
    from sqlalchemy import select
    from app.models import UserSession as UserSessionModel

    try:
        pending = _get_session(qrcode_key)
        pending_purpose = pending.get("purpose") if pending else None
        pending_is_valid = bool(
            pending and pending_purpose in (None, LEGACY_QRCODE_PENDING_PURPOSE)
        )
        if not pending_is_valid and not await _has_legacy_qrcode_pending_state(
            db, qrcode_key
        ):
            raise HTTPException(status_code=404, detail="二维码不存在或已过期")

        bili = BilibiliService()
        try:
            result = await bili.poll_qrcode_status(qrcode_key)
        finally:
            await bili.close()

        response = LoginStatusResponse(
            status=result["status"], message=result["message"]
        )

        # 登录成功
        if result["status"] == "confirmed":
            cookies = normalize_bilibili_cookies(result.get("cookies", {}))

            # 创建会话
            session_id = str(uuid.uuid4())

            # 获取用户信息
            bili_auth = bilibili_service_from_cookies(cookies, BilibiliService)

            user_info_dict = {}
            try:
                try:
                    user_info = await bili_auth.get_user_info()
                finally:
                    await bili_auth.close()

                mid = int(user_info.get("mid") or cookies.get("DedeUserID"))

                user_info_dict = {
                    "mid": mid,
                    "uname": user_info.get("uname"),
                    "face": user_info.get("face"),
                    "level": user_info.get("level_info", {}).get("current_level"),
                }

                # 持久化到数据库
                db_session = UserSessionModel(
                    session_id=session_id,
                    bili_mid=mid,
                    bili_uname=user_info.get("uname"),
                    bili_face=user_info.get("face"),
                    sessdata=_encrypt_session_cookie(cookies["SESSDATA"]),
                    bili_jct=_encrypt_session_cookie(cookies["bili_jct"]),
                    dedeuserid=str(cookies["DedeUserID"]),
                    is_valid=True,
                )
                db.add(db_session)
                await db.commit()

                response.user_info = user_info_dict

            except Exception as e:
                logger.warning(f"获取用户信息失败: {e}")
                response.user_info = {
                    "mid": cookies.get("DedeUserID"),
                    "uname": "未知用户",
                }

            # 内存缓存（为了兼容旧代码）
            _set_session(
                session_id,
                {
                    "cookies": cookies,
                    "user_info": user_info_dict,
                    "refresh_token": result.get("refresh_token"),
                },
            )

            response.session_id = session_id

            # 清理旧的 qrcode_key
            login_sessions.pop(qrcode_key, None)
            await _delete_legacy_qrcode_pending_state(db, qrcode_key)

        elif result["status"] == "expired":
            login_sessions.pop(qrcode_key, None)
            await _delete_legacy_qrcode_pending_state(db, qrcode_key)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"轮询二维码状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"轮询失败: {str(e)}")


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """
    获取会话信息
    """
    session = _get_session(session_id)
    if not session:
        async with get_db_context() as db:
            result = await db.execute(
                select(UserSessionModel).where(
                    UserSessionModel.session_id == session_id
                )
            )
            db_session = result.scalar_one_or_none()
        if not db_session or not db_session.is_valid:
            raise HTTPException(status_code=404, detail="会话不存在或已过期")
        session = {
            "cookies": _cookies_from_db_session(db_session),
            "user_info": {
                "mid": db_session.bili_mid,
                "uname": db_session.bili_uname,
                "face": db_session.bili_face,
            },
        }
        _set_session(session_id, session)

    return {"valid": True, "user_info": session.get("user_info")}


@router.delete("/session/{session_id}")
async def logout(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    退出登录
    """
    login_sessions.pop(session_id, None)
    result = await db.execute(
        select(UserSessionModel).where(UserSessionModel.session_id == session_id)
    )
    db_session = result.scalar_one_or_none()
    if db_session:
        db_session.is_valid = False
        await db.commit()
    return {"message": "已退出登录"}


async def get_session(session_id: str) -> dict:
    """
    获取会话信息（内部使用）
    """
    session = _get_session(session_id)
    if session:
        return session

    async with get_db_context() as db:
        result = await db.execute(
            select(UserSessionModel).where(UserSessionModel.session_id == session_id)
        )
        db_session = result.scalar_one_or_none()
        if not db_session or not db_session.is_valid:
            return None
        session = {
            "cookies": _cookies_from_db_session(db_session),
            "user_info": {
                "mid": db_session.bili_mid,
                "uname": db_session.bili_uname,
                "face": db_session.bili_face,
            },
        }

    if session:
        _set_session(session_id, session)
    return session
