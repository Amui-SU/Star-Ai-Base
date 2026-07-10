"""Markdown export helpers for video notes."""

import re
from datetime import datetime
from typing import Any

from app.models import VideoNote
from app.services.video_note_presenters import VideoNoteSource


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


def _format_timestamp(seconds: Any) -> str:
    total_seconds = max(int(seconds or 0), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _timestamp_url(source: VideoNoteSource, seconds: Any) -> str:
    safe_seconds = max(int(seconds or 0), 0)
    if (source.total_parts or 0) > 1 or (source.page_number or 0) > 1:
        page_number = max(int(source.page_number or 1), 1)
        return f"{source.url}?p={page_number}&t={safe_seconds}"
    return f"{source.url}?t={safe_seconds}"


def _clean_filename(value: str) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "video-note"


def render_video_note_filename(
    note: VideoNote,
    source: VideoNoteSource,
    *,
    template: str | None = None,
) -> str:
    """Render a safe Markdown export filename from note metadata."""

    filename_template = template or note.export_filename_template or "{{title}}.md"
    values = {
        "title": note.title,
        "bvid": note.bvid,
        "up": source.owner_name or "",
        "knowledge_base": str(note.knowledge_base_id),
        "date": _format_date(note.updated_at),
    }
    filename = filename_template
    for key, value in values.items():
        filename = filename.replace(f"{{{{{key}}}}}", str(value))
    if not filename.lower().endswith(".md"):
        filename = f"{filename}.md"
    return _clean_filename(filename)


def _frontmatter(note: VideoNote, source: VideoNoteSource) -> list[str]:
    tags = ", ".join(str(tag) for tag in note.tags_json or [])
    return [
        "---",
        f"title: {note.title}",
        f"bvid: {note.bvid}",
        f"url: {source.url}",
        f"up: {source.owner_name or ''}",
        f"knowledge_base_id: {note.knowledge_base_id}",
        f"tags: [{tags}]",
        f"created: {_format_date(note.created_at)}",
        f"updated: {_format_date(note.updated_at)}",
        "---",
        "",
    ]


def _render_text_items(items: list[Any] | None) -> list[str]:
    lines: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("content") or "").strip()
        else:
            text = str(item).strip()
        if text:
            lines.append(f"- {text}")
    return lines


def _render_timestamp_items(
    items: list[Any] | None,
    source: VideoNoteSource,
) -> list[str]:
    lines: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        seconds = item.get("time", item.get("timestamp", 0))
        text = str(item.get("text") or item.get("content") or "").strip()
        timestamp = _format_timestamp(seconds)
        link = _timestamp_url(source, seconds)
        lines.append(f"- [{timestamp}]({link}) {text}".rstrip())
    return lines


def _render_block(block: dict, source: VideoNoteSource) -> list[str]:
    block_type = str(block.get("type") or "paragraph")
    text = str(block.get("text") or "").strip()

    if block_type == "heading":
        level = min(max(int(block.get("level") or 2), 1), 6)
        return [f"{'#' * level} {text}".rstrip(), ""]
    if block_type in {"paragraph", "ai_summary", "quote"}:
        if not text:
            return []
        prefix = "> " if block_type == "quote" else ""
        return [f"{prefix}{text}", ""]
    if block_type in {"key_points", "questions", "bulleted_list"}:
        lines = _render_text_items(block.get("items"))
        return [*lines, ""] if lines else []
    if block_type == "timestamp_outline":
        lines = _render_timestamp_items(block.get("items"), source)
        return [*lines, ""] if lines else []
    if block_type == "todo":
        checked = "x" if block.get("checked") else " "
        return [f"- [{checked}] {text}".rstrip(), ""]
    if block_type == "divider":
        return ["---", ""]
    if text:
        return [text, ""]
    return []


def render_video_note_markdown(note: VideoNote, source: VideoNoteSource) -> str:
    """Serialize a video note into portable Markdown."""

    lines = _frontmatter(note, source)
    for block in note.blocks_json or []:
        if isinstance(block, dict):
            lines.extend(_render_block(block, source))
    return "\n".join(lines).strip() + "\n"
