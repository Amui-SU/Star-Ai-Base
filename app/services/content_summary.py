"""AI summary parsing helpers for Bilibili content fetching."""

from typing import Optional

from app.services.video_note_ai_text import _coerce_time

TIMESTAMP_KEYS = (
    "timestamp",
    "time",
    "start",
    "from",
    "start_time",
    "startTime",
    "seconds",
)


def _first_present(mapping: dict, *keys: str):
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _timestamp_value(mapping: dict, fallback: int = 0) -> int:
    return _coerce_time(_first_present(mapping, *TIMESTAMP_KEYS), fallback)


def parse_ai_summary_result(result: Optional[dict]) -> Optional[dict]:
    if not result:
        return None

    inner_code = result.get("code", -1)
    if inner_code != 0:
        return None

    model_result = result.get("model_result", {})
    summary = model_result.get("summary", "")
    if not summary:
        return None

    outline = []
    for item in model_result.get("outline", []):
        item_timestamp = _timestamp_value(item)
        outline_item = {
            "title": item.get("title", ""),
            "timestamp": item_timestamp,
            "points": [],
        }
        for point in item.get("part_outline", []):
            outline_item["points"].append(
                {
                    "content": point.get("content", ""),
                    "timestamp": _timestamp_value(point, item_timestamp),
                }
            )
        outline.append(outline_item)

    return {"summary": summary, "outline": outline}


def format_ai_summary_content(summary: dict) -> str:
    parts = [f"AI 摘要：{summary['summary']}"]
    if summary.get("outline"):
        outline_lines = []
        for item in summary["outline"]:
            title_text = item.get("title") or "未命名片段"
            timestamp = item.get("timestamp")
            prefix = (
                f"- {title_text} ({timestamp}s)" if timestamp else f"- {title_text}"
            )
            outline_lines.append(prefix)
            for point in item.get("points") or []:
                point_text = point.get("content")
                if point_text:
                    outline_lines.append(f"  - {point_text}")
        if outline_lines:
            parts.append("分段提纲：\n" + "\n".join(outline_lines))
    return "\n\n".join(parts)
