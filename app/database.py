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
            "workspace_id": "INTEGER",
            "knowledge_base_id": "INTEGER",
            "source_binding_id": "INTEGER",
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
    }

    def ensure_columns(sync_conn):
        for table_name, columns in legacy_columns.items():
            rows = sync_conn.exec_driver_sql(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
            if not rows:
                continue
            existing = {row[1] for row in rows}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    sync_conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )

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
