import pytest
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_init_db_adds_knowledge_scope_columns_to_legacy_tables(test_db_url):
    from app.database import _ensure_sqlite_legacy_columns

    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE favorite_folders (
                id INTEGER PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                media_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                media_count INTEGER
            )
            """
        )

        await _ensure_sqlite_legacy_columns(conn)

        result = await conn.exec_driver_sql("PRAGMA table_info(favorite_folders)")
        columns = {row[1] for row in result.fetchall()}

    await engine.dispose()

    assert {"workspace_id", "knowledge_base_id", "source_binding_id"} <= columns
