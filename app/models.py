"""
Bilibili RAG 知识库系统

数据模型定义
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float
from sqlalchemy import ForeignKey, UniqueConstraint

from app.models_base import Base
from app.models_base import _utc_now
from app.models_content import (
    FavoriteFolder,
    FavoriteVideo,
    IngestionTask,
    VideoCache,
    VideoTitleOverride,
)
from app.models_notes import VideoNote
from app.schemas.api_accounts import (
    ApiAccountCreateRequest,
    ApiAccountDraftValidationRequest,
    ApiAccountDraftValidationResponse,
    ApiAccountResponse,
    ApiAccountUpdateRequest,
)
from app.schemas.auth import (
    AdminPasswordResetResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdateRequest,
    SystemAuthResponse,
    SystemDisplayNameUpdateRequest,
    SystemLoginRequest,
    SystemRegisterRequest,
    SystemUserResponse,
    WorkspaceResponse,
)
from app.schemas.chat import (
    ChatConversationListResponse,
    ChatConversationResponse,
    ChatConversationSaveRequest,
    ChatConversationSummaryResponse,
    ChatHistoryMessageRequest,
    ChatHistoryMessageResponse,
    ChatRequest,
    ChatResponse,
)
from app.schemas.content import (
    ContentSource,
    FavoriteFolderInfo,
    VideoContent,
    VideoInfo,
)
from app.schemas.knowledge_base import (
    KnowledgeBaseBuildRequest,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseChatRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
    KnowledgeScopeFolder,
    KnowledgeScopeOptionsResponse,
    KnowledgeScopeVideo,
)
from app.schemas.source_bindings import (
    LoginStatusResponse,
    QRCodeResponse,
    SourceBindingResponse,
)

# ==================== SQLAlchemy 模型 ====================


class UserSession(Base):
    """用户会话表"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)

    # B站用户信息
    bili_mid = Column(Integer, nullable=True)  # B站用户ID
    bili_uname = Column(String(100), nullable=True)  # B站用户名
    bili_face = Column(String(500), nullable=True)  # 头像URL

    # B站 Cookie 信息；新写入的敏感字段由 auth router 加密，仍兼容旧明文数据读取。
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
    llm_api_source = Column(String(20), nullable=True)
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


class UserApiAccount(Base):
    """Encrypted third-party API credentials owned by a system user."""

    __tablename__ = "user_api_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    provider = Column(String(50), index=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    base_url = Column(String(500), nullable=False)
    model = Column(String(200), nullable=False)
    thinking_config = Column(JSON, nullable=True)
    protocol = Column(String(40), nullable=True)
    auth_scheme = Column(String(40), nullable=True)
    website_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    advanced_config = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    last_validated_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class UsageEvent(Base):
    """Lightweight AI usage audit log, ready for future billing."""

    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    api_account_id = Column(Integer, ForeignKey("user_api_accounts.id"), nullable=True)
    api_source = Column(String(20), default="official", nullable=False)
    feature = Column(String(50), index=True, nullable=False)
    provider = Column(String(50), index=True, nullable=False)
    model = Column(String(200), nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_code = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class VerificationCode(Base):
    """邮箱验证码表"""

    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    code_hash = Column(String(128), nullable=False)  # SHA-256 哈希
    attempts = Column(Integer, default=0)  # 错误尝试次数
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utc_now)


class VerificationIpRateLimit(Base):
    """邮箱验证码 IP 级发送频率窗口。"""

    __tablename__ = "verification_ip_rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(128), unique=True, index=True, nullable=False)
    count = Column(Integer, default=0, nullable=False)
    window_start = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class OAuthPendingState(Base):
    """Short-lived OAuth/QR pending state shared across workers."""

    __tablename__ = "oauth_pending_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_key = Column(String(255), unique=True, index=True, nullable=False)
    purpose = Column(String(50), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=True
    )
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utc_now)


class ChatConversation(Base):
    """Persisted chat conversation owned by a system user."""

    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=True
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True
    )
    title = Column(String(200), nullable=False)
    scope = Column(JSON, nullable=True)
    web_search = Column(Boolean, default=False, nullable=False)
    web_search_provider = Column(String(20), default="auto", nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class ChatMessage(Base):
    """Single persisted message in a chat conversation."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("chat_conversations.id"), index=True, nullable=False
    )
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)
    sources = Column(JSON, nullable=True)
    web_search = Column(JSON, nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utc_now)
