"""Legacy Bilibili login session cache and persistence helpers."""

import time

from sqlalchemy import select

from app.database import get_db_context
from app.models import UserSession as UserSessionModel
from app.security import decrypt_text, encrypt_text

# Legacy login hot cache; persisted rows are the source of truth for durability.
login_sessions: dict = {}

QRCODE_SESSION_TTL = 300
LOGIN_SESSION_TTL = 14 * 86400
ENCRYPTED_COOKIE_PREFIX = "fernet:"


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


def _cleanup_expired_sessions() -> None:
    now = time.time()
    expired_keys = [
        key
        for key, val in login_sessions.items()
        if now - val.get("_created_at", 0) > val.get("_ttl", QRCODE_SESSION_TTL)
    ]
    for key in expired_keys:
        login_sessions.pop(key, None)


def _set_session(key: str, value: dict, ttl: int = LOGIN_SESSION_TTL) -> None:
    value["_created_at"] = time.time()
    value["_ttl"] = ttl
    login_sessions[key] = value


def _get_session(key: str) -> dict | None:
    _cleanup_expired_sessions()
    session = login_sessions.get(key)
    if session is None:
        return None
    now = time.time()
    if now - session.get("_created_at", 0) > session.get("_ttl", LOGIN_SESSION_TTL):
        login_sessions.pop(key, None)
        return None
    return session


async def get_session(session_id: str) -> dict | None:
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

    _set_session(session_id, session)
    return session
