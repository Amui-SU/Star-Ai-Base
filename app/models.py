"""
Bilibili RAG 知识库系统

数据模型定义
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from enum import Enum


def _utc_now() -> datetime:
    """返回 aware UTC 时间（替代已弃用的 datetime.utcnow）"""
    return datetime.now(timezone.utc)


Base = declarative_base()


# ==================== SQLAlchemy 模型 ====================


class VideoCache(Base):
    """视频内容缓存表"""

    __tablename__ = "video_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bvid = Column(String(20), unique=True, index=True, nullable=False)
    cid = Column(Integer, nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    owner_name = Column(String(100), nullable=True)  # UP主名称
    owner_mid = Column(Integer, nullable=True)  # UP主ID

    # 内容
    content = Column(Text, nullable=True)  # 摘要/字幕文本
    content_source = Column(
        String(20), nullable=True
    )  # ai_summary / subtitle / basic_info
    outline_json = Column(JSON, nullable=True)  # 分段提纲

    # 元信息
    duration = Column(Integer, nullable=True)  # 视频时长（秒）
    pic_url = Column(String(500), nullable=True)  # 封面URL

    # 处理状态
    is_processed = Column(Boolean, default=False)  # 是否已处理并加入向量库
    process_error = Column(Text, nullable=True)  # 处理错误信息

    # 多用户归属（向后兼容，旧数据为 NULL）
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True, nullable=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True)
    source_binding_id = Column(Integer, ForeignKey("source_bindings.id"), index=True, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class UserSession(Base):
    """用户会话表"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)

    # B站用户信息
    bili_mid = Column(Integer, nullable=True)  # B站用户ID
    bili_uname = Column(String(100), nullable=True)  # B站用户名
    bili_face = Column(String(500), nullable=True)  # 头像URL

    # Cookie 信息（加密存储更安全，这里简化处理）
    sessdata = Column(Text, nullable=True)
    bili_jct = Column(Text, nullable=True)
    dedeuserid = Column(String(50), nullable=True)

    # 状态
    is_valid = Column(Boolean, default=True)
    last_active_at = Column(DateTime, default=_utc_now)
    created_at = Column(DateTime, default=_utc_now)


class SystemUser(Base):
    """系统用户表"""

    __tablename__ = "system_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class SystemSession(Base):
    """系统登录会话表"""

    __tablename__ = "system_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    session_token_hash = Column(String(128), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    last_seen_at = Column(DateTime, default=_utc_now)


class Workspace(Base):
    """工作区表"""

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    owner_user_id = Column(
        Integer, ForeignKey("system_users.id"), index=True, nullable=False
    )
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class WorkspaceMember(Base):
    """工作区成员表"""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    role = Column(String(20), default="owner", nullable=False)
    created_at = Column(DateTime, default=_utc_now)


class KnowledgeBase(Base):
    """Knowledge base owned by a workspace."""

    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(
        Integer, ForeignKey("system_users.id"), index=True, nullable=False
    )
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class SourceBinding(Base):
    """External source account binding."""

    __tablename__ = "source_bindings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    source_type = Column(String(50), index=True, nullable=False)
    external_account_id = Column(String(100), index=True, nullable=False)
    external_account_name = Column(String(200), nullable=True)
    external_avatar_url = Column(String(500), nullable=True)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    last_verified_at = Column(DateTime, nullable=True)


class SourceCredential(Base):
    """Encrypted credentials for an external source binding."""

    __tablename__ = "source_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=False
    )
    encrypted_payload = Column(Text, nullable=False)
    encryption_version = Column(String(20), default="fernet-v1", nullable=False)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class VerificationCode(Base):
    """邮箱验证码表"""

    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    code_hash = Column(String(128), nullable=False)  # SHA-256 哈希
    attempts = Column(Integer, default=0)  # 错误尝试次数
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utc_now)


class FavoriteFolder(Base):
    """收藏夹记录表"""

    __tablename__ = "favorite_folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)

    # B站收藏夹信息
    media_id = Column(Integer, nullable=False)  # 收藏夹ID
    fid = Column(Integer, nullable=True)  # 原始ID
    title = Column(String(200), nullable=False)
    media_count = Column(Integer, default=0)  # 视频数量

    # 状态
    is_selected = Column(Boolean, default=True)  # 是否选中用于知识库
    last_sync_at = Column(DateTime, nullable=True)

    # 多用户归属（向后兼容，旧数据为 NULL）
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True, nullable=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True)
    source_binding_id = Column(Integer, ForeignKey("source_bindings.id"), index=True, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class FavoriteVideo(Base):
    """收藏夹-视频关联表"""

    __tablename__ = "favorite_videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_id = Column(Integer, index=True, nullable=False)  # 关联 FavoriteFolder.id
    bvid = Column(String(20), index=True, nullable=False)

    # 是否选中（用户可以取消选中某些视频）
    is_selected = Column(Boolean, default=True)

    # 多用户归属（向后兼容，旧数据为 NULL）
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True, nullable=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True)
    source_binding_id = Column(Integer, ForeignKey("source_bindings.id"), index=True, nullable=True)

    created_at = Column(DateTime, default=_utc_now)


class IngestionTask(Base):
    """入库任务表"""

    __tablename__ = "ingestion_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True, nullable=False)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=False)
    source_binding_id = Column(Integer, ForeignKey("source_bindings.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("system_users.id"), nullable=False)

    status = Column(String(20), default="pending", nullable=False)
    progress = Column(Integer, default=0)
    current_step = Column(String(500), nullable=True)
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ==================== Pydantic 模型 (API 用) ====================


class ContentSource(str, Enum):
    """内容来源"""

    AI_SUMMARY = "ai_summary"
    SUBTITLE = "subtitle"
    BASIC_INFO = "basic_info"
    ASR = "asr"


class SystemRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    code: str


class SystemLoginRequest(BaseModel):
    email: str
    password: str


class SystemUserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    avatar_url: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    role: str


class SystemAuthResponse(BaseModel):
    user: SystemUserResponse
    workspace: WorkspaceResponse


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: Optional[str] = None


class KnowledgeBaseSearchRequest(BaseModel):
    query: str
    k: int = 5


class KnowledgeBaseSearchResult(BaseModel):
    content: str
    bvid: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None


class KnowledgeBaseSearchResponse(BaseModel):
    results: list[KnowledgeBaseSearchResult]


class KnowledgeBaseChatRequest(BaseModel):
    question: str
    k: int = 5
    smart_search: bool = False
    deep_think: bool = False


class KnowledgeBaseBuildRequest(BaseModel):
    source_binding_id: int
    folder_ids: list[int]
    exclude_bvids: Optional[list[str]] = None


class KnowledgeBaseBuildResponse(BaseModel):
    task_id: str
    status: str
    workspace_id: int
    knowledge_base_id: int
    source_binding_id: int


class SourceBindingResponse(BaseModel):
    id: int
    source_type: str
    external_account_id: str
    external_account_name: Optional[str] = None
    external_avatar_url: Optional[str] = None
    status: str


class VideoInfo(BaseModel):
    """视频信息"""

    bvid: str
    cid: Optional[int] = None
    title: str
    description: Optional[str] = None
    owner_name: Optional[str] = None
    owner_mid: Optional[int] = None
    duration: Optional[int] = None
    pic_url: Optional[str] = None


class VideoContent(BaseModel):
    """视频内容（含摘要）"""

    bvid: str
    title: str
    content: str
    source: ContentSource
    outline: Optional[list] = None


class QRCodeResponse(BaseModel):
    """二维码响应"""

    qrcode_key: str
    qrcode_url: str
    qrcode_image_base64: str


class LoginStatusResponse(BaseModel):
    """登录状态响应"""

    status: str  # waiting / scanned / confirmed / expired
    message: str
    user_info: Optional[dict] = None
    session_id: Optional[str] = None


class FavoriteFolderInfo(BaseModel):
    """收藏夹信息"""

    media_id: int
    title: str
    media_count: int
    is_selected: bool = True
    is_default: Optional[bool] = None


class ChatRequest(BaseModel):
    """对话请求"""

    question: str
    session_id: Optional[str] = None
    folder_ids: Optional[list[int]] = None  # 指定收藏夹，None 表示全部
    smart_search: bool = False  # 是否启用联网搜索模式（模型支持时生效）
    deep_think: bool = False  # 是否启用深度思考模式（模型支持时生效）


class ChatResponse(BaseModel):
    """对话响应"""

    answer: str
    sources: list[dict]  # 来源视频列表
    thinking: Optional[str] = None  # 思考过程（模型支持时返回）
