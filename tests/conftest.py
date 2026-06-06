import os
import tempfile
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base


@pytest.fixture()
async def test_db_url() -> AsyncIterator[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        yield f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture()
async def test_engine(test_db_url: str):
    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
async def db_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture()
async def client(monkeypatch, db_session_factory) -> AsyncIterator[AsyncClient]:
    import app.database as database

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    monkeypatch.setattr(database, "async_session_factory", db_session_factory)

    from app.main import app

    app.dependency_overrides[database.get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
