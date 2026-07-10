"""Content, favorite, and ingestion ORM models."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy import UniqueConstraint

from app.models_base import Base
from app.models_base import _utc_now


class VideoCache(Base):
    """视频内容缓存表"""

    __tablename__ = "video_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bvid = Column(String(20), index=True, nullable=False)
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

    # 分P元信息（用于AI时间戳功能）
    page_number = Column(Integer, nullable=True)  # 分P编号（1, 2, 3...）
    part_title = Column(String(500), nullable=True)  # 分P原始标题
    total_parts = Column(Integer, nullable=True)  # 总分P数

    # 时间轴数据（用于AI时间戳精确定位）
    subtitle_timeline_json = Column(JSON, nullable=True)  # 完整字幕时间轴

    # 处理状态
    is_processed = Column(Boolean, default=False)  # 是否已处理并加入向量库
    process_error = Column(Text, nullable=True)  # 处理错误信息

    # 多用户归属（向后兼容，旧数据为 NULL）
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=True
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True
    )
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=True
    )

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


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
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=True
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True
    )
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=True
    )

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
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=True
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=True
    )
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=True
    )

    created_at = Column(DateTime, default=_utc_now)


class VideoTitleOverride(Base):
    """用户自定义视频标题"""

    __tablename__ = "video_title_overrides"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "knowledge_base_id",
            "source_binding_id",
            "bvid",
            name="uq_video_title_override_scope",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=False
    )
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=True
    )
    bvid = Column(String(20), index=True, nullable=False)
    custom_title = Column(String(500), nullable=False)
    created_by = Column(Integer, ForeignKey("system_users.id"), nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class IngestionTask(Base):
    """入库任务表"""

    __tablename__ = "ingestion_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=False
    )
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
