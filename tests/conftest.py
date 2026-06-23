import os
import sys
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models import Base
from app.routers.system_auth import _ip_rate_limit


@pytest.fixture(autouse=True)
def isolate_web_search_settings() -> Iterator[None]:
    from app.config import settings

    tracked_settings = {
        "web_search_provider": settings.web_search_provider,
        "tavily_api_key": settings.tavily_api_key,
        "web_search_fallback_html": settings.web_search_fallback_html,
        "tavily_search_depth": settings.tavily_search_depth,
        "http_proxy": settings.http_proxy,
    }
    yield
    for name, value in tracked_settings.items():
        setattr(settings, name, value)


@pytest.fixture(autouse=True)
def isolate_auth_ip_rate_limit() -> Iterator[None]:
    _ip_rate_limit.clear()
    yield
    _ip_rate_limit.clear()


@pytest.fixture()
def test_db_url() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        yield f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture()
async def test_engine(test_db_url: str):
    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
def db_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture()
async def client(monkeypatch, db_session_factory) -> AsyncIterator[AsyncClient]:
    import app.database as database

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    from app.config import settings

    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "admin_emails", "")

    from app.main import app

    missing_override = object()
    previous_override = app.dependency_overrides.get(database.get_db, missing_override)
    app.dependency_overrides[database.get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://testserver",
        ) as test_client:
            yield test_client
    finally:
        if previous_override is missing_override:
            app.dependency_overrides.pop(database.get_db, None)
        else:
            app.dependency_overrides[database.get_db] = previous_override
