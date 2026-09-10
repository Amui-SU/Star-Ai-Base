import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.services.sqlite_legacy_schema import sqlite_create_password_reset_indexes


def test_password_reset_index_keeps_newest_row_and_enforces_one_per_email():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE password_reset_codes (
                id INTEGER PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code_hash VARCHAR(128) NOT NULL,
                attempts INTEGER NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at DATETIME
            )
            """)
        conn.exec_driver_sql("""
            INSERT INTO password_reset_codes (
                id, email, code_hash, attempts, expires_at, created_at
            ) VALUES
                (1, 'member@example.com', 'older', 0, '2030-01-01', '2026-01-01'),
                (2, 'member@example.com', 'newer', 0, '2030-01-01', '2026-01-02')
            """)

        sqlite_create_password_reset_indexes(conn)
        sqlite_create_password_reset_indexes(conn)

        rows = conn.exec_driver_sql(
            "SELECT id, code_hash FROM password_reset_codes ORDER BY id"
        ).fetchall()
        with pytest.raises(IntegrityError):
            conn.exec_driver_sql("""
                INSERT INTO password_reset_codes (
                    email, code_hash, attempts, expires_at
                ) VALUES ('member@example.com', 'third', 0, '2030-01-01')
                """)

    engine.dispose()

    assert rows == [(2, "newer")]
