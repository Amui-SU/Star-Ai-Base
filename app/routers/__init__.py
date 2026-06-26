"""
Bilibili RAG 知识库系统

路由模块初始化
"""

from app.routers import (
    api_accounts,
    auth,
    chat,
    chat_history,
    favorites,
    imports,
    knowledge,
    knowledge_bases,
    local_connection,
    source_bindings,
    system_auth,
)

__all__ = [
    "api_accounts",
    "auth",
    "chat",
    "chat_history",
    "favorites",
    "imports",
    "knowledge",
    "knowledge_bases",
    "local_connection",
    "source_bindings",
    "system_auth",
]
