import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.services.sqlite_legacy_schema import sqlite_add_missing_legacy_columns


def test_legacy_credential_versions_preserve_rows_and_default_new_inserts():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            for table in ("system_users", "system_sessions"):
                conn.exec_driver_sql(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
                conn.exec_driver_sql(f"INSERT INTO {table} (id) VALUES (1)")
            sqlite_add_missing_legacy_columns(conn)
            sqlite_add_missing_legacy_columns(conn)
            for table in ("system_users", "system_sessions"):
                conn.exec_driver_sql(f"INSERT INTO {table} (id) VALUES (2)")
                rows = conn.exec_driver_sql(
                    f"SELECT id, credential_version FROM {table} ORDER BY id"
                ).all()
                assert rows == [(1, 0), (2, 0)]
                with pytest.raises(IntegrityError):
                    conn.exec_driver_sql(
                        f"INSERT INTO {table} (id, credential_version) VALUES (3, NULL)"
                    )
    finally:
        engine.dispose()
