"""Deterministic AI operation shaping for video notes."""

from app.models import VideoNote
from app.schemas.video_notes import VideoNoteAiEditRequest, VideoNoteAiResponse
from app.services.video_note_presenters import VideoNoteSource


def _summary_text(source: VideoNoteSource) -> str:
    content = (source.content or "").strip()
    if content:
        return content
    return f"围绕《{source.title}》整理核心观点，并补充你的理解。"


def _key_points(source: VideoNoteSource) -> list[dict]:
    points: list[dict] = []
    for item in source.outline or []:
        title = str(item.get("title") or "").strip()
        if title:
            points.append({"text": title})
        for point in item.get("points") or []:
            content = str(point.get("content") or "").strip()
            if content:
                points.append({"text": content})
    if points:
        return points[:8]
    return [{"text": "提炼视频中的关键结论"}, {"text": "记录可执行的下一步"}]


def _tag_suggestions(source: VideoNoteSource) -> list[str]:
    tags = ["视频笔记"]
    title = source.title.lower()
    if "ai" in title or "人工智能" in title:
        tags.insert(0, "AI")
    if "学习" in source.title:
        tags.append("学习")
    return tags


def build_summary_suggestions(
    note: VideoNote,
    source: VideoNoteSource,
) -> VideoNoteAiResponse:
    """Build non-mutating operations for seeding AI summary blocks."""

    return VideoNoteAiResponse(
        message="已生成可应用的摘要建议",
        tag_suggestions=_tag_suggestions(source),
        operations=[
            {
                "kind": "replace_or_insert_block",
                "target_block_id": "ai-summary",
                "block": {
                    "id": "ai-summary",
                    "type": "ai_summary",
                    "text": _summary_text(source),
                },
            },
            {
                "kind": "replace_or_insert_block",
                "target_block_id": "key-points",
                "block": {
                    "id": "key-points",
                    "type": "key_points",
                    "items": _key_points(source),
                },
            },
        ],
    )


def build_ai_edit_suggestions(
    note: VideoNote,
    request: VideoNoteAiEditRequest,
) -> VideoNoteAiResponse:
    """Build non-mutating edit operations for the UI to apply with undo."""

    action = request.action.strip().lower()
    instruction = (request.instruction or "").strip()
    if action == "generate_questions":
        return VideoNoteAiResponse(
            message="已生成复盘问题",
            tag_suggestions=[],
            operations=[
                {
                    "kind": "insert_block",
                    "block": {
                        "id": "ai-review-questions",
                        "type": "questions",
                        "items": [
                            {"text": "这个视频最重要的一个观点是什么？"},
                            {"text": "我可以立刻实践的一步是什么？"},
                            {"text": instruction or "还有哪些内容需要回看确认？"},
                        ],
                    },
                }
            ],
        )
    return VideoNoteAiResponse(
        message="已生成编辑建议",
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
