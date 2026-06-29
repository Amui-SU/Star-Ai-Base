"""OAuth state and callback helpers for system authentication routes."""

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
import urllib.parse

from fastapi import Request, Response
from loguru import logger

from app.config import settings

OAUTH_STATE_COOKIE_NAME = "oauth_state_nonce"
_OAUTH_STATE_TTL = 600


def frontend_origin_is_allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse((url or "").strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not parsed.hostname
    ):
        return False

    host = parsed.hostname.lower()
    if host == "localhost":
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return ip.is_loopback or ip.is_private


def normalize_frontend_origin(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urllib.parse.urlparse(url.strip())
    origin = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    if not frontend_origin_is_allowed(origin):
        return None
    return origin


def frontend_url_from_request(request: Request) -> str:
    for header in ("origin", "referer"):
        origin = normalize_frontend_origin(request.headers.get(header))
        if origin:
            return origin
    return "http://localhost:3000"


def frontend_url_from_state(frontend_url: str | None) -> str:
    return normalize_frontend_origin(frontend_url) or "http://localhost:3000"


def oauth_signing_key() -> bytes:
    configured_key = os.getenv("APP_ENCRYPTION_KEY", "").strip()
    if configured_key:
        material = configured_key
    else:
        secrets_material = [
            settings.google_client_secret,
            settings.wechat_client_secret,
            settings.qq_client_secret,
        ]
        material = "|".join(item.strip() for item in secrets_material if item.strip())
    if not material:
        raise RuntimeError(
            "OAuth state signing requires APP_ENCRYPTION_KEY or an OAuth client secret"
        )
    return hashlib.sha256(material.encode("utf-8")).digest()


def make_oauth_state(
    frontend_url: str | None = None,
    redirect_uri: str | None = None,
    nonce: str | None = None,
) -> str:
    """Create a signed OAuth state with the frontend and callback origins."""
    payload = {
        "exp": int(time.time()) + _OAUTH_STATE_TTL,
        "rnd": secrets.token_hex(8),
    }
    if nonce:
        payload["nonce"] = nonce
    safe_frontend_url = frontend_url_from_state(frontend_url)
    if safe_frontend_url:
        payload["frontend_url"] = safe_frontend_url
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    sig = hmac.new(oauth_signing_key(), payload_b64.encode(), hashlib.sha256)
    return f"{payload_b64}.{sig.hexdigest()[:16]}"


def decode_oauth_state(state: str) -> dict | None:
    """Validate and decode a signed OAuth state."""
    try:
        payload_b64, sig = state.rsplit(".", 1)
        expected = hmac.new(
            oauth_signing_key(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            logger.warning("OAuth state signature mismatch")
            return None

        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if time.time() > int(data["exp"]):
            logger.warning(
                f"OAuth state expired: exp={data['exp']}, now={int(time.time())}"
            )
            return None
        return data
    except Exception as exc:
        logger.warning(f"OAuth state parse failed: {type(exc).__name__}: {exc}")
        return None


def verify_oauth_state(state: str) -> bool:
    """Validate OAuth state signature and expiry."""
    return decode_oauth_state(state) is not None


def new_oauth_state_nonce() -> str:
    return secrets.token_urlsafe(24)


def set_oauth_state_cookie(response: Response, nonce: str) -> None:
    secure = (
        bool(settings.session_cookie_secure)
        if settings.session_cookie_secure is not None
        else not settings.debug
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=nonce,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=_OAUTH_STATE_TTL,
        path="/system-auth",
    )


def clear_oauth_state_cookie(response: Response) -> None:
    secure = (
        bool(settings.session_cookie_secure)
        if settings.session_cookie_secure is not None
        else not settings.debug
    )
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        path="/system-auth",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def oauth_state_nonce_is_valid(request: Request, state_data: dict) -> bool:
    nonce = str(state_data.get("nonce") or "")
    cookie_nonce = request.cookies.get(OAUTH_STATE_COOKIE_NAME, "")
    return bool(nonce) and secrets.compare_digest(nonce, cookie_nonce)


def oauth_user_email(provider: str, external_id: str, email: str | None = None) -> str:
    normalized_email = (email or "").strip().lower()
    if normalized_email:
        return normalized_email
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in external_id.lower()).strip(
        "_"
    )
    return f"{provider}_{safe_id or secrets.token_hex(8)}@oauth.local"
