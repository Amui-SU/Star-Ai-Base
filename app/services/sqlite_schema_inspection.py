"""SQLite schema inspection helpers used by legacy migrations."""

from sqlalchemy.engine import Connection


def quote_sqlite_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sqlite_table_columns(sync_conn: Connection, table_name: str) -> set[str]:
    rows = sync_conn.exec_driver_sql(
        f"PRAGMA table_info({quote_sqlite_identifier(table_name)})"
    ).fetchall()
    return {row[1] for row in rows}


def sqlite_has_unique_bvid_index(sync_conn: Connection) -> bool:
    if not sqlite_table_columns(sync_conn, "video_cache"):
        return False
    indexes = sync_conn.exec_driver_sql('PRAGMA index_list("video_cache")').fetchall()
    for index in indexes:
        index_name = index[1]
        is_unique = bool(index[2])
        if not is_unique:
            continue
        indexed_columns = [
            row[2]
            for row in sync_conn.exec_driver_sql(
                f"PRAGMA index_info({quote_sqlite_identifier(index_name)})"
            ).fetchall()
            if row[2] is not None
        ]
        if indexed_columns == ["bvid"]:
            return True
    return False


def sqlite_select_expr(
    existing: set[str], column_name: str, fallback: str = "NULL"
) -> str:
    return quote_sqlite_identifier(column_name) if column_name in existing else fallback
