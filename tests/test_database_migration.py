import pytest
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_init_db_adds_knowledge_scope_columns_to_legacy_tables(test_db_url):
    from app.database import _ensure_sqlite_legacy_columns
    from app.services.sqlite_legacy_schema import ensure_sqlite_legacy_columns

    assert _ensure_sqlite_legacy_columns is ensure_sqlite_legacy_columns

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


@pytest.mark.asyncio
async def test_init_db_migrates_video_cache_unique_bvid_to_scoped_rows(test_db_url):
    from app.database import _ensure_sqlite_legacy_columns

    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE video_cache (
                id INTEGER PRIMARY KEY,
                bvid VARCHAR(20) UNIQUE NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                is_processed BOOLEAN,
                workspace_id INTEGER,
                knowledge_base_id INTEGER,
                source_binding_id INTEGER
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE favorite_videos (
                id INTEGER PRIMARY KEY,
                folder_id INTEGER NOT NULL,
                bvid VARCHAR(20) NOT NULL,
                workspace_id INTEGER,
                knowledge_base_id INTEGER,
                source_binding_id INTEGER
            )
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO video_cache (
                id, bvid, title, content, is_processed, workspace_id, knowledge_base_id
            ) VALUES (
                1, 'BV1shared', 'Original title', 'cached content', 1, 1, 10
            )
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO favorite_videos (
                id, folder_id, bvid, workspace_id, knowledge_base_id, source_binding_id
            ) VALUES
                (1, 101, 'BV1shared', 1, 10, NULL),
                (2, 202, 'BV1shared', 2, 20, NULL)
            """
        )

        await _ensure_sqlite_legacy_columns(conn)

        await conn.exec_driver_sql(
            """
            INSERT INTO video_cache (
                bvid, title, content, is_processed, workspace_id, knowledge_base_id
            ) VALUES (
                'BV1shared', 'Second title', 'second content', 1, 3, 30
            )
            """
        )
        rows = (
            await conn.exec_driver_sql(
                """
                SELECT bvid, title, content, workspace_id, knowledge_base_id
                FROM video_cache
                WHERE bvid = 'BV1shared'
                ORDER BY workspace_id, knowledge_base_id
                """
            )
        ).fetchall()

    await engine.dispose()

    assert [(row[0], row[1], row[2], row[3], row[4]) for row in rows] == [
        ("BV1shared", "Original title", "cached content", 1, 10),
        ("BV1shared", "Original title", "cached content", 2, 20),
        ("BV1shared", "Second title", "second content", 3, 30),
    ]


@pytest.mark.asyncio
async def test_init_db_adds_usage_event_source_columns_to_legacy_table(test_db_url):
    from app.database import _ensure_sqlite_legacy_columns

    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE usage_events (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                feature VARCHAR(50) NOT NULL,
                provider VARCHAR(50) NOT NULL,
                model VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
            """
        )

        await _ensure_sqlite_legacy_columns(conn)

        result = await conn.exec_driver_sql("PRAGMA table_info(usage_events)")
        columns = {row[1] for row in result.fetchall()}

    await engine.dispose()

    assert {
        "api_account_id",
        "api_source",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost",
        "error_code",
        "created_at",
    } <= columns


@pytest.mark.asyncio
async def test_init_db_adds_video_cache_part_metadata_columns(test_db_url):
    from app.database import _ensure_sqlite_legacy_columns

    engine = create_async_engine(test_db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE video_cache (
                id INTEGER PRIMARY KEY,
                bvid VARCHAR(20) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                is_processed BOOLEAN,
                workspace_id INTEGER,
                knowledge_base_id INTEGER,
                source_binding_id INTEGER
            )
            """
        )

        await _ensure_sqlite_legacy_columns(conn)

        result = await conn.exec_driver_sql("PRAGMA table_info(video_cache)")
        columns = {row[1] for row in result.fetchall()}

    await engine.dispose()

    assert {
        "page_number",
        "part_title",
        "total_parts",
        "subtitle_timeline_json",
    } <= columns
