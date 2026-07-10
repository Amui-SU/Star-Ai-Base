"""Content and favorite-folder API schemas."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ContentSource(str, Enum):
    """Content source."""

    AI_SUMMARY = "ai_summary"
    SUBTITLE = "subtitle"
    BASIC_INFO = "basic_info"
    ASR = "asr"


class VideoInfo(BaseModel):
    """Video metadata."""

    bvid: str
    cid: Optional[int] = None
    title: str
    description: Optional[str] = None
    owner_name: Optional[str] = None
    owner_mid: Optional[int] = None
    duration: Optional[int] = None
    pic_url: Optional[str] = None


class VideoContent(BaseModel):
    """Video content including summary/transcript text."""

    bvid: str
    title: str
    content: str
    source: ContentSource
    outline: Optional[list] = None
    subtitle_timeline: Optional[list[dict]] = None  # 字幕时间轴数据


class FavoriteFolderInfo(BaseModel):
    """Favorite folder API payload."""

    media_id: int
    title: str
    media_count: int
    is_selected: bool = True
    is_default: Optional[bool] = None
