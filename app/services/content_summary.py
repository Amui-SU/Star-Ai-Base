"""AI summary parsing helpers for Bilibili content fetching."""

from typing import Optional


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
        outline_item = {
            "title": item.get("title", ""),
            "timestamp": item.get("timestamp", 0),
            "points": [],
        }
        for point in item.get("part_outline", []):
            outline_item["points"].append(
                {
                    "content": point.get("content", ""),
                    "timestamp": point.get("timestamp", 0),
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
