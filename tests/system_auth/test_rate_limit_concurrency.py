import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import VerificationIpRateLimit
from app.services.system_auth_codes import check_ip_rate_limit
from app.time_utils import utc_now_naive


@pytest.mark.asyncio
async def test_preloaded_rate_limit_cannot_overwrite_concurrent_grants(
    db_session_factory,
):
    async with db_session_factory() as db:
        assert await check_ip_rate_limit(db, "shared-ip")
    async with db_session_factory() as stale_db:
        stale = await stale_db.scalar(select(VerificationIpRateLimit))
        async with db_session_factory() as other_db:
            assert await check_ip_rate_limit(other_db, "shared-ip")
            assert await check_ip_rate_limit(other_db, "shared-ip")
        assert not await check_ip_rate_limit(stale_db, "shared-ip")
        assert stale.ip_address == "shared-ip"
    async with db_session_factory() as db:
        assert (await db.scalar(select(VerificationIpRateLimit))).count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", ["missing", "expired", "active"])
async def test_concurrent_rate_limit_grants_exact_remaining_quota(
    db_session_factory, initial
):
    if initial != "missing":
        async with db_session_factory() as db:
            db.add(
                VerificationIpRateLimit(
                    ip_address="shared-ip",
                    count=1 if initial == "active" else 3,
                    window_start=utc_now_naive()
                    - timedelta(seconds=120 if initial == "expired" else 0),
                    updated_at=utc_now_naive(),
                )
            )
            await db.commit()

    async def attempt():
        async with db_session_factory() as db:
            return await check_ip_rate_limit(db, "shared-ip")

    results = await asyncio.gather(*(attempt() for _ in range(8)))
    assert results.count(True) == (2 if initial == "active" else 3)
    async with db_session_factory() as db:
        assert (await db.scalar(select(VerificationIpRateLimit))).count == 3
