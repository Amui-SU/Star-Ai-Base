import base64
import binascii
import hashlib
import os
import secrets
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Response
from passlib.context import CryptContext

from app.config import settings
from app.time_utils import utc_now

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=True,
)
SESSION_COOKIE_NAME = "system_session"
SESSION_TTL_DAYS = 14
_DEV_ENCRYPTION_KEY_SEED = b"bilibili-rag-dev-encryption-key"
_fernet_instance = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expires_at() -> datetime:
    return utc_now() + timedelta(days=SESSION_TTL_DAYS)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite="lax",
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=_session_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def _session_cookie_secure() -> bool:
    configured = settings.session_cookie_secure
    if configured is not None:
        return bool(configured)
    return not settings.debug


def _derive_fernet_key(secret: str) -> bytes:
    raw = secret.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(raw)
    except (binascii.Error, ValueError):
        decoded = b""
    if len(decoded) == 32:
        return raw
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


def _fernet_key() -> bytes:
    raw_key = os.getenv("APP_ENCRYPTION_KEY", "")
    if raw_key:
        return _derive_fernet_key(raw_key)
    if settings.debug:
        return base64.urlsafe_b64encode(
            hashlib.sha256(_DEV_ENCRYPTION_KEY_SEED).digest()
        )
    raise RuntimeError("APP_ENCRYPTION_KEY must be set in production")


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(_fernet_key())
    return _fernet_instance


def encrypt_text(value: str) -> str:
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("encrypted payload cannot be decrypted") from exc
