"""Shared text cleanup helpers for video note AI services."""

import re


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
    if isinstance(value, str):
        stripped = value.strip()
        if ":" in stripped:
            parts = stripped.split(":")
            if 2 <= len(parts) <= 3:
                try:
                    seconds = 0
                    for part in parts:
                        seconds = seconds * 60 + int(float(part))
                    return max(0, seconds)
                except ValueError:
                    return fallback
    try:
        return max(0, int(value or fallback))
    except (TypeError, ValueError):
        return fallback


def _safe_list(value: object) -> list:
    return value if isinstance(value, list) else []
