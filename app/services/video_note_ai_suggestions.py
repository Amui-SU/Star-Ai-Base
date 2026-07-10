"""AI suggestion shaping for video note UI operations."""

from typing import Literal

from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest, VideoNoteAiResponse
from app.services.video_note_ai_text import (
    _append_unique,
    _clean_text,
    _coerce_time,
    _safe_list,
)
from app.services.video_note_presenters import VideoNoteSource

AiStatus = Literal["generated", "unavailable", "failed", "official"]
EMPTY_TIMESTAMPS_MESSAGE = "ℹ 当前视频暂无可用时间点数据，已生成基础框架"
TIMESTAMP_KEYS = (
    "time",
    "timestamp",
    "start",
    "from",
    "start_time",
    "startTime",
    "seconds",
)


def _summary_text(source: VideoNoteSource) -> str:
    content = _clean_text(source.content, max_length=900)
    if content:
        return content
    description = _clean_text(getattr(source, "description", None), max_length=600)
    if description:
        return description
    return f"围绕《{source.title}》整理核心观点，并补充你的理解。"


def _key_points(source: VideoNoteSource) -> list[dict]:
    points: list[dict] = []
    for item in source.outline or []:
        if not isinstance(item, dict):
            continue
        _append_unique(points, item.get("title"))
        for point in item.get("points") or []:
            if isinstance(point, dict):
                _append_unique(points, point.get("content") or point.get("text"))
    if points:
        return points[:8]

    for candidate in (
        getattr(source, "description", None),
        source.content,
        source.title,
    ):
        text = _clean_text(candidate, max_length=180)
        if text:
            return [{"text": text}]
    return []


def _tag_suggestions(source: VideoNoteSource, payload_tags: object = None) -> list[str]:
    tags: list[str] = []
    for tag in _safe_list(payload_tags):
        normalized = _clean_text(tag, max_length=24)
        if normalized and normalized.lower() not in {item.lower() for item in tags}:
            tags.append(normalized)
    if tags:
        return tags[:5]
    tags.append("视频笔记")
    title = source.title.lower()
    if ("ai" in title or "人工智能" in title) and "AI" not in tags:
        tags.insert(0, "AI")
    if "学习" in source.title and "学习" not in tags:
        tags.append("学习")
    return tags[:5]


def _payload_strings(payload: dict | None, *keys: str) -> list[dict]:
    if not payload:
        return []
    for key in keys:
        values = payload.get(key)
        if isinstance(values, list):
            items: list[dict] = []
            for value in values:
                if isinstance(value, dict):
                    _append_unique(items, value.get("text") or value.get("content"))
                else:
                    _append_unique(items, value)
            if items:
                return items
    return []


def _first_present(mapping: dict, *keys: str) -> object:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _timestamp_from_mapping(mapping: dict, fallback: int = 0) -> int:
    return _coerce_time(_first_present(mapping, *TIMESTAMP_KEYS), fallback)


def _payload_timestamps(payload: dict | None) -> list[dict]:
    if not payload:
        return []
    values = payload.get("timestamps") or payload.get("items")
    if not isinstance(values, list):
        return []
    items: list[dict] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        _append_unique(
            items,
            value.get("text") or value.get("title") or value.get("content"),
            time=_timestamp_from_mapping(value),
        )
    return items[:12]


def _has_specific_timestamps(items: list[dict]) -> bool:
    return any(_timestamp_from_mapping(item) > 0 for item in items)


def _message_for(action: str, status: AiStatus) -> str:
    if status == "official":
        return {
            "summary": "✓ 已根据 B 站官方章节生成摘要建议",
            "questions": "✓ 已根据 B 站官方章节生成复盘问题",
            "timestamps": "✓ 已根据 B 站官方章节生成时间戳提纲",
            "edit": "✓ 已根据 B 站官方章节生成编辑建议",
        }[action]
    if status == "generated":
        return {
            "summary": "✓ AI 已重新生成摘要和关键观点",
            "questions": "✓ AI 已重新生成复盘问题",
            "timestamps": "✓ AI 已重新生成时间戳提纲",
            "edit": "✓ AI 已生成编辑建议",
        }[action]
    if status == "failed":
        return "⚠ AI 生成失败，已根据入库内容提供基础建议；请稍后重试或检查模型配置"
    return "ℹ AI 模型未连接，已根据入库内容提供基础建议；配置模型后可获得更好效果"


def build_summary_suggestions(
    note: VideoNote,
    source: VideoNoteSource,
    *,
    ai_payload: dict | None = None,
    ai_status: AiStatus = "unavailable",
) -> VideoNoteAiResponse:
    """Build non-mutating operations for seeding summary blocks."""

    summary = _clean_text(
        (ai_payload or {}).get("summary") or (ai_payload or {}).get("text"),
        max_length=900,
    )
    if not summary:
        summary = _summary_text(source)
    key_points = _payload_strings(ai_payload, "key_points", "points", "takeaways")
    if not key_points:
        key_points = _key_points(source)

    return VideoNoteAiResponse(
        message=_message_for("summary", ai_status),
        tag_suggestions=_tag_suggestions(source, (ai_payload or {}).get("tags")),
        operations=[
            {
                "kind": "replace_or_insert_block",
                "target_block_id": "ai-summary",
                "block": {
                    "id": "ai-summary",
                    "type": "ai_summary",
                    "text": summary,
                },
            },
            {
                "kind": "replace_or_insert_block",
                "target_block_id": "key-points",
                "block": {
                    "id": "key-points",
                    "type": "key_points",
                    "items": key_points,
                },
            },
        ],
    )


def _question_items(
    source: VideoNoteSource | None,
    ai_payload: dict | None = None,
) -> list[dict]:
    ai_items = _payload_strings(ai_payload, "questions", "items")
    if ai_items:
        return ai_items[:7]

    items: list[dict] = []
    if source:
        if source.title:
            _append_unique(
                items,
                f"《{source.title}》最值得复述给别人的核心结论是什么？",
            )
        for point in _key_points(source)[:4]:
            text = str(point.get("text") or "").strip()
            if text:
                _append_unique(
                    items,
                    f"关于「{text}」，我能否用自己的话复述并举一个例子？",
                )
        source_text = (
            getattr(source, "description", None) or source.content or source.title or ""
        )
        excerpt = _clean_text(source_text, max_length=72)
        if excerpt:
            _append_unique(items, f"「{excerpt}」对我的下一步行动有什么启发？")
    for text in [
        "这个视频最重要的一个观点是什么？",
        "我可以立刻实践的一步是什么？",
        "还有哪些内容需要回看确认？",
    ]:
        _append_unique(items, text)
    return items[:6]


def _timestamp_items(
    source: VideoNoteSource | None,
    ai_payload: dict | None = None,
    bilibili_timestamps: list[dict] | None = None,
) -> list[dict]:
    # 优先使用 B 站官方章节
    if bilibili_timestamps:
        items: list[dict] = []
        for item in bilibili_timestamps:
            if not isinstance(item, dict):
                continue
            _append_unique(
                items,
                item.get("text") or item.get("content") or item.get("title"),
                time=_timestamp_from_mapping(item),
            )
        if items and _has_specific_timestamps(items):
            return items[:12]

    # 其次使用 AI 生成的时间戳
    ai_items = _payload_timestamps(ai_payload)
    if ai_items and _has_specific_timestamps(ai_items):
        return ai_items

    # 再次尝试使用数据库中的 outline
    items: list[dict] = []
    if source:
        for index, entry in enumerate(source.outline or []):
            if not isinstance(entry, dict):
                continue
            timestamp = _timestamp_from_mapping(entry)
            title = str(entry.get("title") or f"片段 {index + 1}").strip()
            _append_unique(items, title, time=timestamp)
            for point in entry.get("points") or []:
                if not isinstance(point, dict):
                    continue
                point_text = str(
                    point.get("content") or point.get("text") or ""
                ).strip()
                if point_text:
                    _append_unique(
                        items,
                        point_text,
                        time=_timestamp_from_mapping(point, timestamp),
                    )
    if items and _has_specific_timestamps(items):
        return items[:12]

    # 如果都没有具体时间戳，但有内容，生成基础框架时间戳
    if items and source and source.duration:
        # 根据视频时长智能分配时间戳
        duration = source.duration
        num_items = min(len(items), 8)
        for i in range(num_items):
            if items[i].get("time", 0) == 0:
                # 均匀分布时间戳
                items[i]["time"] = int((duration * i) / max(num_items - 1, 1))
        return items[:num_items]

    return []


def build_ai_edit_suggestions(
    note: VideoNote,
    request: VideoNoteAiEditRequest,
    source: VideoNoteSource | None = None,
    *,
    ai_payload: dict | None = None,
    ai_status: AiStatus = "unavailable",
    bilibili_timestamps: list[dict] | None = None,
) -> VideoNoteAiResponse:
    """Build non-mutating edit operations for the UI to apply with undo."""

    action = request.action.strip().lower()
    instruction = (request.instruction or "").strip()
    if action == "generate_questions":
        return VideoNoteAiResponse(
            message=_message_for("questions", ai_status),
            tag_suggestions=[],
            operations=[
                {
                    "kind": "replace_or_insert_block",
                    "target_block_id": "questions",
                    "block": {
                        "id": "questions",
                        "type": "questions",
                        "items": _question_items(source, ai_payload),
                    },
                }
            ],
        )
    if action == "generate_timestamps":
        timestamp_items = _timestamp_items(
            source,
            ai_payload,
            bilibili_timestamps,
        )
        return VideoNoteAiResponse(
            message=(
                _message_for("timestamps", ai_status)
                if timestamp_items
                else EMPTY_TIMESTAMPS_MESSAGE
            ),
            tag_suggestions=[],
            operations=[
                {
                    "kind": "replace_or_insert_block",
                    "target_block_id": "timestamp-outline",
                    "block": {
                        "id": "timestamp-outline",
                        "type": "timestamp_outline",
                        "items": timestamp_items,
                    },
                }
            ],
        )
    return VideoNoteAiResponse(
        message=_message_for("edit", ai_status),
        tag_suggestions=[],
        operations=[
            {
                "kind": "insert_block",
                "block": {
                    "id": "ai-edit-suggestion",
                    "type": "paragraph",
                    "text": instruction or "补充这里的理解、例子或待办。",
                },
            }
        ],
    )
