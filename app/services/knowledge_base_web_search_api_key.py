"""Knowledge-base web-search API key resolution."""

from collections.abc import Awaitable, Callable
from typing import Any


async def resolve_web_search_api_key(
    db: Any,
    user: Any,
    *,
    enabled: bool,
    provider: str,
    resolve_optional_user_api_credentials: Callable[..., Awaitable[Any]],
) -> str | None:
    if not enabled or provider == "html":
        return None
    credential = await resolve_optional_user_api_credentials(db, user, "tavily")
    return credential.api_key if credential else None
