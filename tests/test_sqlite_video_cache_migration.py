from sqlalchemy import create_engine

from app.services.sqlite_video_cache_migration import (
    sqlite_clone_scoped_video_cache_rows,
    sqlite_create_video_cache_indexes,
    sqlite_rebuild_video_cache_without_unique_bvid,
)


def test_sqlite_video_cache_migration_rebuilds_legacy_unique_bvid_table():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE video_cache (
                id INTEGER PRIMARY KEY,
                bvid VARCHAR(20) UNIQUE NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                is_processed BOOLEAN
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO video_cache (id, bvid, title, content, is_processed)
            VALUES (1, 'BV1', 'Title', 'Content', 1)
            """
        )

        sqlite_rebuild_video_cache_without_unique_bvid(conn)
        sqlite_create_video_cache_indexes(conn)
        conn.exec_driver_sql(
            """
            INSERT INTO video_cache (
                bvid, title, content, is_processed, workspace_id, knowledge_base_id
            ) VALUES ('BV1', 'Scoped', 'Scoped Content', 1, 2, 20)
            """
        )
        rows = conn.exec_driver_sql(
            """
            SELECT bvid, title, content, workspace_id, knowledge_base_id
            FROM video_cache
            WHERE bvid = 'BV1'
            ORDER BY id
            """
        ).fetchall()

    engine.dispose()

    assert [(row[0], row[1], row[2], row[3], row[4]) for row in rows] == [
        ("BV1", "Title", "Content", None, None),
        ("BV1", "Scoped", "Scoped Content", 2, 20),
    ]


def test_sqlite_video_cache_migration_clones_scoped_rows_from_favorite_videos():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE video_cache (
                id INTEGER PRIMARY KEY,
                bvid VARCHAR(20) NOT NULL,
                cid INTEGER,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                owner_name VARCHAR(100),
                owner_mid INTEGER,
                content TEXT,
                content_source VARCHAR(20),
                outline_json JSON,
                duration INTEGER,
                pic_url VARCHAR(500),
                is_processed BOOLEAN,
                process_error TEXT,
                workspace_id INTEGER,
                knowledge_base_id INTEGER,
                source_binding_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
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
        conn.exec_driver_sql(
            """
            INSERT INTO video_cache (
                id, bvid, title, content, is_processed, workspace_id, knowledge_base_id
            ) VALUES (1, 'BV1', 'Original', 'Cached', 1, 1, 10)
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO favorite_videos (
                id, folder_id, bvid, workspace_id, knowledge_base_id, source_binding_id
            ) VALUES
                (1, 100, 'BV1', 1, 10, NULL),
                (2, 200, 'BV1', 2, 20, NULL)
            """
        )

        sqlite_clone_scoped_video_cache_rows(conn)
        rows = conn.exec_driver_sql(
            """
            SELECT bvid, title, content, workspace_id, knowledge_base_id
            FROM video_cache
            WHERE bvid = 'BV1'
            ORDER BY workspace_id, knowledge_base_id
            """
        ).fetchall()

    engine.dispose()

    assert [(row[0], row[1], row[2], row[3], row[4]) for row in rows] == [
        ("BV1", "Original", "Cached", 1, 10),
        ("BV1", "Original", "Cached", 2, 20),
    ]
