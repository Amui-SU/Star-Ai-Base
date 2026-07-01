from sqlalchemy import create_engine

from app.services.sqlite_schema_inspection import (
    quote_sqlite_identifier,
    sqlite_has_unique_bvid_index,
    sqlite_select_expr,
    sqlite_table_columns,
)


def test_quote_sqlite_identifier_escapes_embedded_quotes():
    assert quote_sqlite_identifier('video"cache') == '"video""cache"'


def test_sqlite_select_expr_quotes_existing_columns_and_uses_fallbacks():
    existing = {"bvid", "title"}

    assert sqlite_select_expr(existing, "bvid") == '"bvid"'
    assert sqlite_select_expr(existing, "created_at", "CURRENT_TIMESTAMP") == (
        "CURRENT_TIMESTAMP"
    )


def test_sqlite_table_columns_returns_empty_for_missing_table():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        assert sqlite_table_columns(conn, "missing") == set()

    engine.dispose()


def test_sqlite_has_unique_bvid_index_detects_legacy_unique_column_index():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE video_cache (
                id INTEGER PRIMARY KEY,
                bvid VARCHAR(20) UNIQUE NOT NULL,
                title VARCHAR(500) NOT NULL
            )
            """
        )

        assert sqlite_has_unique_bvid_index(conn) is True

    engine.dispose()
