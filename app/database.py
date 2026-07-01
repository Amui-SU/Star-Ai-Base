"""
Bilibili RAG 知识库系统

数据库管理模块
"""

from contextlib import asynccontextmanager
import os

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models import Base
from app.services.sqlite_legacy_schema import (
    SQLITE_LEGACY_COLUMNS,
    ensure_sqlite_legacy_columns,
    ensure_sqlite_legacy_schema_sync,
    quote_sqlite_identifier,
    sqlite_add_missing_legacy_columns,
    sqlite_clone_scoped_video_cache_rows,
    sqlite_create_api_account_indexes,
    sqlite_create_chat_history_indexes,
    sqlite_create_video_cache_indexes,
    sqlite_has_unique_bvid_index,
    sqlite_rebuild_video_cache_without_unique_bvid,
    sqlite_select_expr,
    sqlite_table_columns,
)


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
        await ensure_sqlite_legacy_columns(conn)


_ensure_sqlite_legacy_columns = ensure_sqlite_legacy_columns
_ensure_sqlite_legacy_schema_sync = ensure_sqlite_legacy_schema_sync
_quote_sqlite_identifier = quote_sqlite_identifier
_sqlite_add_missing_legacy_columns = sqlite_add_missing_legacy_columns
_sqlite_clone_scoped_video_cache_rows = sqlite_clone_scoped_video_cache_rows
_sqlite_create_api_account_indexes = sqlite_create_api_account_indexes
_sqlite_create_chat_history_indexes = sqlite_create_chat_history_indexes
_sqlite_create_video_cache_indexes = sqlite_create_video_cache_indexes
_sqlite_has_unique_bvid_index = sqlite_has_unique_bvid_index
_sqlite_rebuild_video_cache_without_unique_bvid = (
    sqlite_rebuild_video_cache_without_unique_bvid
)
_sqlite_select_expr = sqlite_select_expr
_sqlite_table_columns = sqlite_table_columns


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
