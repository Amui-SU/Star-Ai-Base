"""AI operation shaping and model prompts for video notes."""

import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest
from app.services.chat_completion import (
    build_thinking_completion_options,
    create_chat_completion_async,
)
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.video_note_ai_suggestions import (
    build_ai_edit_suggestions,
    build_summary_suggestions,
)
from app.services.video_note_ai_text import _clean_text, _coerce_time
from app.services.video_note_presenters import VideoNoteSource

GENERATED_BLOCK_IDS = {
    "ai-summary",
    "key-points",
    "ai-review-questions",
    "timestamp-outline",
}


def _outline_context(source: VideoNoteSource) -> str:
    lines: list[str] = []
    for index, entry in enumerate(source.outline or [], start=1):
        if not isinstance(entry, dict):
            continue
        title = _clean_text(entry.get("title") or f"片段 {index}", max_length=120)
        timestamp = _coerce_time(entry.get("timestamp"))
        if title:
            lines.append(f"- {timestamp}s {title}")
        for point in entry.get("points") or []:
            if not isinstance(point, dict):
                continue
            point_text = _clean_text(
                point.get("content") or point.get("text"),
                max_length=150,
            )
            if point_text:
                point_time = _coerce_time(point.get("timestamp"), timestamp)
                lines.append(f"  - {point_time}s {point_text}")
    return "\n".join(lines[:40])


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
    if (source.total_parts or 0) > 1:
        page_number = source.page_number or 1
        parts.append(f"当前分P：P{page_number}/{source.total_parts}")
        if source.part_title:
            parts.append(f"当前分P标题：{source.part_title}")
    if source.duration:
        minutes = source.duration // 60
        seconds = source.duration % 60
        duration_label = "当前分P时长" if (source.total_parts or 0) > 1 else "视频时长"
        parts.append(f"{duration_label}：{minutes}分{seconds}秒（{source.duration}秒）")
    if source.owner_name:
        parts.append(f"UP 主：{source.owner_name}")
    description = _clean_text(getattr(source, "description", None), max_length=1200)
    if description:
        parts.append(f"视频简介：{description}")
    content = _clean_text(source.content, max_length=4000)
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
                "不要复述用户按钮文案、不要输出提示词、不要输出 Markdown 代码块。"
                "时间戳生成规则：如果视频资料中有明确时间点就精确使用；如果没有，根据内容在视频中的相对位置合理推断（如：开头段落推断为0-60秒，中段推断为视频时长的30%-70%，结尾段落推断为80%-100%）。"
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
        output_schema='{"summary":"一段 120-280 字摘要","key_points":["3-8 条关键观点"],"tags":["2-5 个标签"]}',
        requirements=(
            "- 摘要要说明视频的核心主题、解决的问题、关键方法和可执行的结论。\n"
            "- 关键观点必须是从视频资料中提炼出的具体、可验证的内容，每条观点简洁明确。\n"
            "- 标签用简短词语（2-5字），反映视频的主题、领域或类型，不要超过 5 个。\n"
            "- 优先使用视频中的实际内容，而不是泛泛的总结。"
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
                "- 每个问题都要能推动用户：(1) 复述核心观点 (2) 联系实际案例 (3) 制定行动计划。\n"
                "- 问题要具体、可回答，避免泛泛而谈。\n"
                "- 优先围绕视频的关键内容提问，而不是通用问题。\n"
                "- 不要沿用旧问题，不要继续追加旧内容。\n"
                '- 不要出现"生成复盘问题"等按钮文案。'
            ),
            exclude_block_ids={"questions", "ai-review-questions"},
        )
    if action == "generate_timestamps":
        part_time_requirement = ""
        if (source.total_parts or 0) > 1:
            part_time_requirement = (
                "\n- 当前视频是分P视频，time 必须是当前分P内的秒数，"
                "不要累计前面分P的时长。"
            )
        return _messages(
            note=note,
            source=source,
            task="重新生成时间戳提纲",
            output_schema='{"timestamps":[{"time":0,"text":"片段标题"},{"time":120,"text":"另一个片段"}]}',
            requirements=(
                "- time 是秒数整数。如果视频资料中有明确时间点就使用它；如果没有，可以根据内容顺序合理推断（如：开头0秒、1/3处推断为视频时长的1/3、中间推断为时长一半等）。\n"
                f"{part_time_requirement}\n"
                "- text 要概括该时间点的内容主题，简洁明确（5-15字）。\n"
                "- 生成 4-10 个有代表性的时间戳，覆盖视频的主要内容节点。\n"
                "- 时间戳应该递增排序，从 0 秒开始到视频结尾附近。\n"
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
        temperature=0.5,
        max_tokens=2000,
        **build_thinking_completion_options(dict(llm_config)),
    )
    content = response.choices[0].message.content or ""
    return _extract_json_object(content)
