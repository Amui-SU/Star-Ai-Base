"""Persistent pending-state helpers for source binding flows."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthPendingState
from app.time_utils import utc_now_naive


async def create_pending_state(
    db: AsyncSession,
    *,
    state_key: str,
    purpose: str,
    user_id: int,
    ttl_seconds: int,
) -> None:
    now = utc_now_naive()
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.expires_at < now)
    )
    existing = await db.execute(
        select(OAuthPendingState).where(OAuthPendingState.state_key == state_key)
    )
    pending = existing.scalar_one_or_none()
    expires_at = now + timedelta(seconds=ttl_seconds)
    if pending is None:
        db.add(
            OAuthPendingState(
                state_key=state_key,
                purpose=purpose,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
    else:
        pending.purpose = purpose
        pending.user_id = user_id
        pending.expires_at = expires_at
    await db.commit()


async def get_pending_state(
    db: AsyncSession,
    *,
    state_key: str,
    purpose: str,
    user_id: int,
) -> OAuthPendingState | None:
    now = utc_now_naive()
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.expires_at < now)
    )
    result = await db.execute(
        select(OAuthPendingState).where(OAuthPendingState.state_key == state_key)
    )
    pending = result.scalar_one_or_none()
    await db.commit()
    if (
        pending is None
        or pending.purpose != purpose
        or pending.user_id != user_id
        or pending.expires_at <= now
    ):
        return None
    return pending


async def delete_pending_state(db: AsyncSession, state_key: str) -> None:
    await db.execute(
        delete(OAuthPendingState).where(OAuthPendingState.state_key == state_key)
    )
    await db.commit()
