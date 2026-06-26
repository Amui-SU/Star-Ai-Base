"""
Bilibili RAG 知识库系统

数据库管理模块
"""

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from contextlib import asynccontextmanager
from app.config import settings
from app.models import Base
import os


# 确保数据目录存在
os.makedirs("data", exist_ok=True)

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """初始化数据库（创建表）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_legacy_columns(conn)


async def _ensure_sqlite_legacy_columns(conn: AsyncConnection) -> None:
    """Add columns introduced after the first local SQLite schema."""
    if conn.engine.url.get_backend_name() != "sqlite":
        return

    legacy_columns = {
        "video_cache": {
            "cid": "INTEGER",
            "description": "TEXT",
            "owner_name": "VARCHAR(100)",
            "owner_mid": "INTEGER",
            "content_source": "VARCHAR(20)",
            "outline_json": "JSON",
            "duration": "INTEGER",
            "pic_url": "VARCHAR(500)",
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

    def ensure_columns(sync_conn):
        def quote_identifier(value: str) -> str:
            return '"' + value.replace('"', '""') + '"'

        def table_columns(table_name: str) -> set[str]:
            rows = sync_conn.exec_driver_sql(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            ).fetchall()
            return {row[1] for row in rows}

        for table_name, columns in legacy_columns.items():
            existing = table_columns(table_name)
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    sync_conn.exec_driver_sql(
                        f"ALTER TABLE {quote_identifier(table_name)} "
                        f"ADD COLUMN {quote_identifier(column_name)} {column_type}"
                    )

        def has_unique_bvid_index() -> bool:
            if not table_columns("video_cache"):
                return False
            indexes = sync_conn.exec_driver_sql(
                'PRAGMA index_list("video_cache")'
            ).fetchall()
            for index in indexes:
                index_name = index[1]
                is_unique = bool(index[2])
                if not is_unique:
                    continue
                indexed_columns = [
                    row[2]
                    for row in sync_conn.exec_driver_sql(
                        f"PRAGMA index_info({quote_identifier(index_name)})"
                    ).fetchall()
                    if row[2] is not None
                ]
                if indexed_columns == ["bvid"]:
                    return True
            return False

        def select_expr(
            existing: set[str], column_name: str, fallback: str = "NULL"
        ) -> str:
            return (
                quote_identifier(column_name) if column_name in existing else fallback
            )

        def rebuild_video_cache_without_unique_bvid() -> None:
            existing = table_columns("video_cache")
            if not existing or not has_unique_bvid_index():
                return

            sync_conn.exec_driver_sql('DROP TABLE IF EXISTS "video_cache_new"')
            sync_conn.exec_driver_sql(
                """
                CREATE TABLE "video_cache_new" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            columns = [
                "id",
                "bvid",
                "cid",
                "title",
                "description",
                "owner_name",
                "owner_mid",
                "content",
                "content_source",
                "outline_json",
                "duration",
                "pic_url",
                "is_processed",
                "process_error",
                "workspace_id",
                "knowledge_base_id",
                "source_binding_id",
                "created_at",
                "updated_at",
            ]
            expressions = [
                select_expr(existing, "id"),
                select_expr(existing, "bvid"),
                select_expr(existing, "cid"),
                select_expr(existing, "title", "COALESCE(bvid, '')"),
                select_expr(existing, "description"),
                select_expr(existing, "owner_name"),
                select_expr(existing, "owner_mid"),
                select_expr(existing, "content"),
                select_expr(existing, "content_source"),
                select_expr(existing, "outline_json"),
                select_expr(existing, "duration"),
                select_expr(existing, "pic_url"),
                select_expr(existing, "is_processed", "0"),
                select_expr(existing, "process_error"),
                select_expr(existing, "workspace_id"),
                select_expr(existing, "knowledge_base_id"),
                select_expr(existing, "source_binding_id"),
                select_expr(existing, "created_at", "CURRENT_TIMESTAMP"),
                select_expr(existing, "updated_at", "CURRENT_TIMESTAMP"),
            ]
            sync_conn.exec_driver_sql(
                f"""
                INSERT INTO "video_cache_new" ({", ".join(quote_identifier(c) for c in columns)})
                SELECT {", ".join(expressions)}
                FROM "video_cache"
                """
            )
            sync_conn.exec_driver_sql('DROP TABLE "video_cache"')
            sync_conn.exec_driver_sql(
                'ALTER TABLE "video_cache_new" RENAME TO "video_cache"'
            )

        def create_video_cache_indexes() -> None:
            if not table_columns("video_cache"):
                return
            sync_conn.exec_driver_sql(
                'CREATE INDEX IF NOT EXISTS "ix_video_cache_bvid" '
                'ON "video_cache" ("bvid")'
            )
            sync_conn.exec_driver_sql(
                'CREATE INDEX IF NOT EXISTS "ix_video_cache_workspace_id" '
                'ON "video_cache" ("workspace_id")'
            )
            sync_conn.exec_driver_sql(
                'CREATE INDEX IF NOT EXISTS "ix_video_cache_knowledge_base_id" '
                'ON "video_cache" ("knowledge_base_id")'
            )
            sync_conn.exec_driver_sql(
                'CREATE INDEX IF NOT EXISTS "ix_video_cache_source_binding_id" '
                'ON "video_cache" ("source_binding_id")'
            )
            sync_conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "ix_video_cache_scope_bvid"
                ON "video_cache" (
                    "workspace_id",
                    "knowledge_base_id",
                    COALESCE("source_binding_id", -1),
                    "bvid"
                )
                WHERE "workspace_id" IS NOT NULL
                  AND "knowledge_base_id" IS NOT NULL
                """
            )

        def clone_scoped_video_cache_rows() -> None:
            if not table_columns("video_cache") or not table_columns("favorite_videos"):
                return
            sync_conn.exec_driver_sql(
                """
                WITH desired AS (
                    SELECT
                        fv.bvid AS bvid,
                        fv.workspace_id AS workspace_id,
                        fv.knowledge_base_id AS knowledge_base_id,
                        fv.source_binding_id AS source_binding_id
                    FROM favorite_videos fv
                    WHERE fv.workspace_id IS NOT NULL
                      AND fv.knowledge_base_id IS NOT NULL
                    GROUP BY
                        fv.bvid,
                        fv.workspace_id,
                        fv.knowledge_base_id,
                        COALESCE(fv.source_binding_id, -1)
                ),
                source AS (
                    SELECT
                        desired.bvid AS bvid,
                        desired.workspace_id AS workspace_id,
                        desired.knowledge_base_id AS knowledge_base_id,
                        desired.source_binding_id AS source_binding_id,
                        COALESCE(
                            MIN(
                                CASE
                                    WHEN src.workspace_id = desired.workspace_id
                                     AND src.knowledge_base_id = desired.knowledge_base_id
                                     AND COALESCE(src.source_binding_id, -1) =
                                         COALESCE(desired.source_binding_id, -1)
                                    THEN src.id
                                END
                            ),
                            MIN(src.id)
                        ) AS source_cache_id
                    FROM desired
                    JOIN video_cache src
                      ON src.bvid = desired.bvid
                    GROUP BY
                        desired.bvid,
                        desired.workspace_id,
                        desired.knowledge_base_id,
                        COALESCE(desired.source_binding_id, -1)
                )
                INSERT INTO video_cache (
                    bvid,
                    cid,
                    title,
                    description,
                    owner_name,
                    owner_mid,
                    content,
                    content_source,
                    outline_json,
                    duration,
                    pic_url,
                    is_processed,
                    process_error,
                    workspace_id,
                    knowledge_base_id,
                    source_binding_id,
                    created_at,
                    updated_at
                )
                SELECT
                    src.bvid,
                    src.cid,
                    src.title,
                    src.description,
                    src.owner_name,
                    src.owner_mid,
                    src.content,
                    src.content_source,
                    src.outline_json,
                    src.duration,
                    src.pic_url,
                    src.is_processed,
                    src.process_error,
                    source.workspace_id,
                    source.knowledge_base_id,
                    source.source_binding_id,
                    src.created_at,
                    src.updated_at
                FROM source
                JOIN video_cache src
                  ON src.id = source.source_cache_id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM video_cache vc
                    WHERE vc.bvid = source.bvid
                      AND vc.workspace_id = source.workspace_id
                      AND vc.knowledge_base_id = source.knowledge_base_id
                      AND COALESCE(vc.source_binding_id, -1) =
                          COALESCE(source.source_binding_id, -1)
                )
                """
            )

        def create_api_account_indexes() -> None:
            if table_columns("user_api_accounts"):
                sync_conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS "ix_user_api_accounts_user_provider" '
                    'ON "user_api_accounts" ("user_id", "provider")'
                )
                sync_conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS "ix_user_api_accounts_user_default" '
                    'ON "user_api_accounts" ("user_id", "is_default")'
                )
            if table_columns("usage_events"):
                sync_conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS "ix_usage_events_user_feature" '
                    'ON "usage_events" ("user_id", "feature")'
                )

        def create_chat_history_indexes() -> None:
            if table_columns("chat_conversations"):
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
            if table_columns("chat_messages"):
                sync_conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS "ix_chat_messages_conversation_id" '
                    'ON "chat_messages" ("conversation_id")'
                )
                sync_conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS "ix_chat_messages_user_id" '
                    'ON "chat_messages" ("user_id")'
                )

        rebuild_video_cache_without_unique_bvid()
        create_video_cache_indexes()
        clone_scoped_video_cache_rows()
        create_api_account_indexes()
        create_chat_history_indexes()

    await conn.run_sync(ensure_columns)


async def get_db() -> AsyncSession:
    """获取数据库会话（用于 FastAPI 依赖注入）"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """获取数据库会话（用于上下文管理器）"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
