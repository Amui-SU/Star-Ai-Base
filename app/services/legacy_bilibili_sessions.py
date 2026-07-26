"""Bilibili 绑定二维码流程的进程内会话热缓存。"""

import time

# 进程内热缓存；二维码 pending state 的持久化以数据库为准。
login_sessions: dict = {}

QRCODE_SESSION_TTL = 300
LOGIN_SESSION_TTL = 14 * 86400


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
