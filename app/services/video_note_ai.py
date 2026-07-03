"""AI operation shaping and model prompts for video notes."""

import json
import re
from collections.abc import Callable, Mapping
from typing import Any, Literal

from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest, VideoNoteAiResponse
from app.services.chat_completion import (
    build_thinking_completion_options,
    create_chat_completion_async,
)
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.video_note_presenters import VideoNoteSource

AiStatus = Literal["generated", "unavailable", "failed"]

GENERATED_BLOCK_IDS = {
    "ai-summary",
    "key-points",
    "ai-review-questions",
    "timestamp-outline",
}

PROMPT_LEAK_PHRASES = {
    "生成摘要",
    "生成复盘问题",
    "生成问题",
    "生成时间戳",
    "生成时间戳提纲",
    "提炼视频中的关键结论",
    "记录可执行的下一步",
}


def _clean_text(value: object, *, max_length: int = 280) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[\s\-*•·]+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if text in PROMPT_LEAK_PHRASES:
        return ""
    if any(text.startswith(phrase) for phrase in PROMPT_LEAK_PHRASES):
        return ""
    return text[:max_length].strip()


def _append_unique(items: list[dict], text: object, **extra: object) -> None:
    normalized = _clean_text(text)
    if not normalized:
        return
    if any(str(item.get("text") or "").strip() == normalized for item in items):
        return
    items.append({"text": normalized, **extra})


def _coerce_time(value: object, fallback: int = 0) -> int:
    try:
        return max(0, int(value or fallback))
    except (TypeError, ValueError):
        return fallback


def _safe_list(value: object) -> list:
    return value if isinstance(value, list) else []


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


def _outline_context(source: VideoNoteSource) -> str:
    lines: list[str] = []
    for index, entry in enumerate(source.outline or [], start=1):
        if not isinstance(entry, dict):
            continue
        title = _clean_text(entry.get("title") or f"片段 {index}", max_length=80)
        timestamp = _coerce_time(entry.get("timestamp"))
        if title:
            lines.append(f"- {timestamp}s {title}")
        for point in entry.get("points") or []:
            if not isinstance(point, dict):
                continue
            point_text = _clean_text(
                point.get("content") or point.get("text"),
                max_length=100,
            )
            if point_text:
                point_time = _coerce_time(point.get("timestamp"), timestamp)
                lines.append(f"  - {point_time}s {point_text}")
    return "\n".join(lines[:24])


def _note_context(note: VideoNote, *, exclude_block_ids: set[str]) -> str:
    lines: list[str] = []
    for block in note.blocks_json or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        if block_id in exclude_block_ids:
            continue
        text = _clean_text(block.get("text"), max_length=180)
        if text:
            lines.append(f"- {block.get('type') or 'block'}: {text}")
        for item in block.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_text = _clean_text(
                item.get("text") or item.get("content"),
                max_length=140,
            )
            if item_text:
                lines.append(f"  - {item_text}")
        if len(lines) >= 16:
            break
    return "\n".join(lines)


def _source_context(source: VideoNoteSource) -> str:
    parts = [
        f"视频标题：{source.title}",
        f"视频链接：{source.url}",
    ]
    if source.owner_name:
        parts.append(f"UP 主：{source.owner_name}")
    description = _clean_text(getattr(source, "description", None), max_length=900)
    if description:
        parts.append(f"视频简介：{description}")
    content = _clean_text(source.content, max_length=2500)
    if content:
        parts.append(f"已入库摘要/正文：{content}")
    outline = _outline_context(source)
    if outline:
        parts.append(f"已入库时间线：\n{outline}")
    return "\n\n".join(parts)


def _messages(
    *,
    note: VideoNote,
    source: VideoNoteSource,
    task: str,
    output_schema: str,
    requirements: str,
    exclude_block_ids: set[str],
) -> list[dict]:
    note_context = _note_context(note, exclude_block_ids=exclude_block_ids)
    user_parts = [
        f"任务：{task}",
        "视频资料：",
        _source_context(source),
    ]
    if note_context:
        user_parts.extend(["当前笔记中可参考的用户内容：", note_context])
    user_parts.extend(
        [
            "要求：",
            requirements,
            "只返回一个 JSON 对象，结构如下：",
            output_schema,
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "你是一个严谨的视频学习笔记助手。你必须基于给定视频资料生成可直接放入笔记的内容。"
                "不要复述用户按钮文案、不要输出提示词、不要输出 Markdown 代码块、不要编造不存在的时间点。"
                "内容不足时要根据已有标题/简介/摘要提出具体可验证的内容，不要写占位句。"
            ),
        },
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def build_summary_messages(note: VideoNote, source: VideoNoteSource) -> list[dict]:
    return _messages(
        note=note,
        source=source,
        task="为视频笔记重新生成摘要、关键观点和标签",
        output_schema='{"summary":"一段 120-220 字摘要","key_points":["3-8 条关键观点"],"tags":["1-5 个标签"]}',
        requirements=(
            "- 摘要要说明视频解决的问题、核心方法和适合记录的结论。\n"
            "- 关键观点必须是从视频资料中提炼出的具体内容。\n"
            "- 标签用短词，不要超过 5 个。"
        ),
        exclude_block_ids={"ai-summary", "key-points"},
    )


def build_ai_edit_messages(
    note: VideoNote,
    request: VideoNoteAiEditRequest,
    source: VideoNoteSource,
) -> list[dict] | None:
    action = request.action.strip().lower()
    if action == "generate_questions":
        return _messages(
            note=note,
            source=source,
            task="重新生成复盘问题",
            output_schema='{"questions":["4-7 个复盘问题"]}',
            requirements=(
                "- 每个问题都要能推动用户复述、迁移或行动。\n"
                "- 不要沿用旧问题，不要继续追加旧内容。\n"
                "- 不要出现“生成复盘问题”等按钮文案。"
            ),
            exclude_block_ids={"questions", "ai-review-questions"},
        )
    if action == "generate_timestamps":
        return _messages(
            note=note,
            source=source,
            task="重新生成时间戳提纲",
            output_schema='{"timestamps":[{"time":0,"text":"片段标题"}]}',
            requirements=(
                "- time 必须是秒数整数；如果资料没有明确时间点，只能使用 0。\n"
                "- text 要概括片段内容，不要写占位词。\n"
                "- 不要沿用旧时间戳块，不要继续追加旧内容。"
            ),
            exclude_block_ids={"timestamp-outline"},
        )
    return None


def _extract_json_object(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed


async def generate_video_note_ai_json(
    messages: list[dict],
    llm_config: Mapping[str, Any],
    get_llm_client: Callable[[Mapping[str, Any]], Any] = _get_llm_client,
) -> dict:
    client = get_llm_client(llm_config)
    response = await create_chat_completion_async(
        client,
        model=llm_config["model"],
        messages=messages,
        temperature=0.35,
        max_tokens=1200,
        **build_thinking_completion_options(dict(llm_config)),
    )
    content = response.choices[0].message.content or ""
    return _extract_json_object(content)


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
            time=_coerce_time(value.get("time") or value.get("timestamp")),
        )
    return items[:12]


def _message_for(action: str, status: AiStatus) -> str:
    if status == "generated":
        return {
            "summary": "已由 AI 重新生成摘要",
            "questions": "已由 AI 重新生成复盘问题",
            "timestamps": "已由 AI 重新生成时间戳提纲",
            "edit": "已由 AI 生成编辑建议",
        }[action]
    if status == "failed":
        return "AI 生成失败，已根据入库内容提供基础建议；请稍后重试"
    return "AI 模型未连接，已根据入库内容提供基础建议；配置模型后可重新生成"


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
) -> list[dict]:
    ai_items = _payload_timestamps(ai_payload)
    if ai_items:
        return ai_items

    items: list[dict] = []
    if source:
        for index, entry in enumerate(source.outline or []):
            if not isinstance(entry, dict):
                continue
            timestamp = _coerce_time(entry.get("timestamp"))
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
                        time=_coerce_time(point.get("timestamp"), timestamp),
                    )
    if items:
        return items[:12]
    if source and source.title:
        return [{"time": 0, "text": f"围绕《{source.title}》梳理视频主线"}]
    return []


def build_ai_edit_suggestions(
    note: VideoNote,
    request: VideoNoteAiEditRequest,
    source: VideoNoteSource | None = None,
    *,
    ai_payload: dict | None = None,
    ai_status: AiStatus = "unavailable",
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
        return VideoNoteAiResponse(
            message=_message_for("timestamps", ai_status),
            tag_suggestions=[],
            operations=[
                {
                    "kind": "replace_or_insert_block",
                    "target_block_id": "timestamp-outline",
                    "block": {
                        "id": "timestamp-outline",
                        "type": "timestamp_outline",
                        "items": _timestamp_items(source, ai_payload),
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
