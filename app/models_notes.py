"""Video note ORM models."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.models_base import Base
from app.models_base import _utc_now


class VideoNote(Base):
    """Private user note bound to a video inside one knowledge base."""

    __tablename__ = "video_notes"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            "knowledge_base_id",
            "bvid",
            name="uq_video_note_user_workspace_kb_bvid",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("system_users.id"), index=True, nullable=False)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), index=True, nullable=False
    )
    knowledge_base_id = Column(
        Integer, ForeignKey("knowledge_bases.id"), index=True, nullable=False
    )
    bvid = Column(String(20), index=True, nullable=False)
    source_binding_id = Column(
        Integer, ForeignKey("source_bindings.id"), index=True, nullable=True
    )
    title = Column(String(500), nullable=False)
    template_id = Column(String(80), default="standard", nullable=False)
    blocks_json = Column(JSON, nullable=False)
    tags_json = Column(JSON, default=list, nullable=False)
    summary_status = Column(String(40), default="not_generated", nullable=False)
    summary_generated_at = Column(DateTime, nullable=True)
    export_filename_template = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
