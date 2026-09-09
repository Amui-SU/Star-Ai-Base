"""SQLite legacy schema maintenance helpers."""

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from app.services.sqlite_schema_inspection import (
    quote_sqlite_identifier,
    sqlite_has_unique_bvid_index,
    sqlite_select_expr,
    sqlite_table_columns,
)
from app.services.sqlite_video_cache_migration import (
    sqlite_clone_scoped_video_cache_rows,
    sqlite_create_video_cache_indexes,
    sqlite_rebuild_video_cache_without_unique_bvid,
)

SQLITE_LEGACY_COLUMNS: dict[str, dict[str, str]] = {
    "video_cache": {
        "cid": "INTEGER",
        "description": "TEXT",
        "owner_name": "VARCHAR(100)",
        "owner_mid": "INTEGER",
        "content_source": "VARCHAR(20)",
        "outline_json": "JSON",
        "duration": "INTEGER",
        "pic_url": "VARCHAR(500)",
        "page_number": "INTEGER",
        "part_title": "VARCHAR(500)",
        "total_parts": "INTEGER",
        "subtitle_timeline_json": "JSON",
        "process_error": "TEXT",
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "source_binding_id": "INTEGER",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "favorite_folders": {
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "source_binding_id": "INTEGER",
    },
    "favorite_videos": {
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "source_binding_id": "INTEGER",
    },
    "video_title_overrides": {
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "source_binding_id": "INTEGER",
    },
    "ingestion_tasks": {
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "source_binding_id": "INTEGER",
    },
    "user_api_accounts": {
        "thinking_config": "JSON",
        "protocol": "VARCHAR(40)",
        "auth_scheme": "VARCHAR(40)",
        "website_url": "VARCHAR(500)",
        "notes": "TEXT",
        "advanced_config": "JSON",
        "enabled": "BOOLEAN",
        "is_default": "BOOLEAN",
        "last_validated_at": "DATETIME",
        "last_error": "TEXT",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "usage_events": {
        "api_account_id": "INTEGER",
        "api_source": "VARCHAR(20)",
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "total_tokens": "INTEGER",
        "estimated_cost": "FLOAT",
        "error_code": "VARCHAR(120)",
        "created_at": "DATETIME",
    },
    "system_users": {
        "llm_api_source": "VARCHAR(20)",
        "credential_version": "INTEGER NOT NULL DEFAULT 0",
    },
    "system_sessions": {
        "credential_version": "INTEGER NOT NULL DEFAULT 0",
    },
    "chat_conversations": {
        "user_id": "INTEGER",
        "workspace_id": "INTEGER",
        "knowledge_base_id": "INTEGER",
        "title": "VARCHAR(200)",
        "scope": "JSON",
        "web_search": "BOOLEAN",
        "web_search_provider": "VARCHAR(20)",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "chat_messages": {
        "conversation_id": "INTEGER",
        "user_id": "INTEGER",
        "role": "VARCHAR(20)",
        "content": "TEXT",
        "thinking": "TEXT",
        "sources": "JSON",
        "web_search": "JSON",
        "sequence": "INTEGER",
        "created_at": "DATETIME",
    },
}


def sqlite_add_missing_legacy_columns(sync_conn: Connection) -> None:
    for table_name, columns in SQLITE_LEGACY_COLUMNS.items():
        existing = sqlite_table_columns(sync_conn, table_name)
        if not existing:
            continue
        for column_name, column_type in columns.items():
            if column_name not in existing:
                sync_conn.exec_driver_sql(
                    f"ALTER TABLE {quote_sqlite_identifier(table_name)} "
                    f"ADD COLUMN {quote_sqlite_identifier(column_name)} {column_type}"
                )


def sqlite_create_api_account_indexes(sync_conn: Connection) -> None:
    if sqlite_table_columns(sync_conn, "user_api_accounts"):
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_user_api_accounts_user_provider" '
            'ON "user_api_accounts" ("user_id", "provider")'
        )
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_user_api_accounts_user_default" '
            'ON "user_api_accounts" ("user_id", "is_default")'
        )
    if sqlite_table_columns(sync_conn, "usage_events"):
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_usage_events_user_feature" '
            'ON "usage_events" ("user_id", "feature")'
        )


def sqlite_create_chat_history_indexes(sync_conn: Connection) -> None:
    if sqlite_table_columns(sync_conn, "chat_conversations"):
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_chat_conversations_user_id" '
            'ON "chat_conversations" ("user_id")'
        )
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_chat_conversations_knowledge_base_id" '
            'ON "chat_conversations" ("knowledge_base_id")'
        )
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_chat_conversations_updated_at" '
            'ON "chat_conversations" ("updated_at")'
        )
    if sqlite_table_columns(sync_conn, "chat_messages"):
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_chat_messages_conversation_id" '
            'ON "chat_messages" ("conversation_id")'
        )
        sync_conn.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_chat_messages_user_id" '
            'ON "chat_messages" ("user_id")'
        )


def sqlite_create_password_reset_indexes(sync_conn: Connection) -> None:
    if not sqlite_table_columns(sync_conn, "password_reset_codes"):
        return
    sync_conn.exec_driver_sql("""
        DELETE FROM password_reset_codes
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM password_reset_codes
            GROUP BY email
        )
        """)
    sync_conn.exec_driver_sql(
        'CREATE UNIQUE INDEX IF NOT EXISTS "ux_password_reset_codes_email" '
        'ON "password_reset_codes" ("email")'
    )


def ensure_sqlite_legacy_schema_sync(sync_conn: Connection) -> None:
    sqlite_add_missing_legacy_columns(sync_conn)
    sqlite_rebuild_video_cache_without_unique_bvid(sync_conn)
    sqlite_create_video_cache_indexes(sync_conn)
    sqlite_clone_scoped_video_cache_rows(sync_conn)
    sqlite_create_api_account_indexes(sync_conn)
    sqlite_create_chat_history_indexes(sync_conn)
    sqlite_create_password_reset_indexes(sync_conn)


async def ensure_sqlite_legacy_columns(conn: AsyncConnection) -> None:
    """Add columns introduced after the first local SQLite schema."""
    if conn.engine.url.get_backend_name() != "sqlite":
        return

    await conn.run_sync(ensure_sqlite_legacy_schema_sync)
