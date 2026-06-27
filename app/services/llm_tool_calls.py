import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class LLMToolRunResult:
    messages: list[dict]
    answer: str | None = None
    thinking: str = ""


def tool_call_to_dict(tool_call: Any) -> dict:
    if isinstance(tool_call, dict):
        return tool_call
    function = getattr(tool_call, "function", None)
    return {
        "id": getattr(tool_call, "id", ""),
        "type": getattr(tool_call, "type", "function"),
        "function": {
            "name": getattr(function, "name", ""),
            "arguments": getattr(function, "arguments", "{}"),
        },
    }


def message_to_openai_dict(message: Any) -> dict:
    if isinstance(message, dict):
        raw = message
    elif hasattr(message, "model_dump"):
        raw = message.model_dump(exclude_none=True)
    elif hasattr(message, "dict"):
        raw = message.dict(exclude_none=True)
    else:
        raw = {"role": "assistant", "content": getattr(message, "content", "") or ""}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            raw["tool_calls"] = [
                tool_call_to_dict(tool_call) for tool_call in tool_calls
            ]

    result = {
        "role": raw.get("role") or "assistant",
        "content": raw.get("content") or "",
    }
    if raw.get("tool_calls"):
        result["tool_calls"] = raw["tool_calls"]
    return result


def tool_call_id(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        return str(tool_call.get("id") or "")
    return str(getattr(tool_call, "id", "") or "")


def tool_call_function(tool_call: Any) -> tuple[str, Any]:
    if isinstance(tool_call, dict):
        function = tool_call.get("function") or {}
        return str(function.get("name") or ""), function.get("arguments") or "{}"
    function = getattr(tool_call, "function", None)
    return str(getattr(function, "name", "") or ""), (
        getattr(function, "arguments", "{}") or "{}"
    )


def extract_dsml_text_tool_calls(content: str) -> tuple[str, list[dict]]:
    if "<｜｜DSML｜｜tool_calls>" not in content:
        return content, []

    tool_calls: list[dict] = []

    def collect_tool_calls(match: re.Match) -> str:
        block = match.group(1)
        for invoke_index, invoke_match in enumerate(
            re.finditer(
                r'<｜｜DSML｜｜invoke\s+name="([^"]+)">(.*?)</｜｜DSML｜｜invoke>',
                block,
                flags=re.DOTALL,
            ),
            start=len(tool_calls) + 1,
        ):
            arguments = {
                param_match.group(1): param_match.group(2).strip()
                for param_match in re.finditer(
                    r'<｜｜DSML｜｜parameter\s+name="([^"]+)"(?:\s+string="true")?>(.*?)</｜｜DSML｜｜parameter>',
                    invoke_match.group(2),
                    flags=re.DOTALL,
                )
            }
            tool_calls.append(
                {
                    "id": f"dsml_call_{invoke_index}",
                    "type": "function",
                    "function": {
                        "name": invoke_match.group(1).strip(),
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return ""

    visible_content = re.sub(
        r"<｜｜DSML｜｜tool_calls>(.*?)</｜｜DSML｜｜tool_calls>",
        collect_tool_calls,
        content,
        flags=re.DOTALL,
    ).strip()
    return visible_content, tool_calls


def contains_dsml_tool_call_text(content: str) -> bool:
    return "<｜｜DSML｜｜tool_calls>" in (content or "")


def append_no_more_tool_calls_instruction(messages: list[dict]) -> list[dict]:
    return [
        *messages,
        {
            "role": "system",
            "content": (
                "工具调用阶段已经结束。不要再输出工具调用、DSML、XML 或 JSON 工具请求；"
                "请直接基于已有知识库资料和工具返回结果，用 Markdown 回答用户问题。"
            ),
        },
    ]


def normalize_tool_arguments(parsed: dict) -> dict:
    normalized = dict(parsed)
    if normalized.get("query"):
        return normalized

    for key in ("search_query", "keyword", "keywords", "q"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            normalized["query"] = value.strip()
            normalized.pop(key, None)
            return normalized

    queries = normalized.get("queries")
    if isinstance(queries, list):
        query = " ".join(str(item).strip() for item in queries if str(item).strip())
        if query:
            normalized["query"] = query
            normalized.pop("queries", None)
    elif isinstance(queries, str) and queries.strip():
        normalized["query"] = queries.strip()
        normalized.pop("queries", None)
    return normalized


def parse_tool_arguments(raw_arguments: Any) -> dict:
    if isinstance(raw_arguments, dict):
        return normalize_tool_arguments(raw_arguments)
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return normalize_tool_arguments(parsed) if isinstance(parsed, dict) else {}


async def append_tool_call_results(
    working_messages: list[dict],
    message: Any,
    tool_calls: list[Any],
    *,
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    remaining_tool_calls: int,
) -> tuple[list[dict], int]:
    executed_tool_calls = 0
    working_messages.append(message_to_openai_dict(message))
    for tool_call in tool_calls:
        call_id = tool_call_id(tool_call)
        name, raw_arguments = tool_call_function(tool_call)
        handler = tool_handlers.get(name)
        if executed_tool_calls >= remaining_tool_calls:
            executed_tool_calls += 1
            content = {
                "error": "tool_call_limit_exceeded",
                "message": "联网搜索次数已达到上限",
            }
        elif handler is None:
            executed_tool_calls += 1
            content = {
                "error": "unknown_tool",
                "message": f"工具 {name or 'unknown'} 不可用",
            }
        else:
            executed_tool_calls += 1
            content = await handler(parse_tool_arguments(raw_arguments))
        working_messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(content, ensure_ascii=False),
            }
        )
    return working_messages, executed_tool_calls


def extract_thinking_and_answer(
    raw_answer: str, reasoning_content: str | None = None
) -> tuple[str, str]:
    """Extract native reasoning content and final visible answer."""
    thinking = (reasoning_content or "").strip()
    answer = (raw_answer or "").strip()

    if thinking:
        return thinking, answer

    pattern = re.compile(
        r"<(?:thinking|think)>(.*?)</(?:thinking|think)>", re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(answer)
    if not match:
        return "", answer

    extracted = (match.group(1) or "").strip()
    cleaned = pattern.sub("", answer).strip()
    return extracted, cleaned
