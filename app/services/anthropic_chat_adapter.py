"""OpenAI-shaped facade for the Anthropic Messages SDK."""

import json
from types import SimpleNamespace
from typing import Any


def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _as_blocks(content: Any) -> list[dict]:
    if isinstance(content, list):
        return content
    if content is None or content == "":
        return []
    return [{"type": "text", "text": str(content)}]


def _convert_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
    systems: list[str] = []
    converted: list[dict] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            systems.append(str(message.get("content") or ""))
            continue
        if role == "tool":
            role = "user"
            content = [
                {
                    "type": "tool_result",
                    "tool_use_id": message.get("tool_call_id") or "tool_call",
                    "content": str(message.get("content") or ""),
                }
            ]
        else:
            content = _as_blocks(message.get("content"))
            if role == "assistant":
                for tool_call in message.get("tool_calls") or []:
                    function = (
                        tool_call.get("function", {})
                        if isinstance(tool_call, dict)
                        else getattr(tool_call, "function", None)
                    )
                    if not isinstance(function, dict):
                        function = {
                            "name": getattr(function, "name", "tool"),
                            "arguments": getattr(function, "arguments", "{}"),
                        }
                    arguments = function.get("arguments") or "{}"
                    try:
                        tool_input = json.loads(arguments)
                    except (TypeError, json.JSONDecodeError):
                        tool_input = {"value": str(arguments)}
                    tool_id = (
                        tool_call.get("id")
                        if isinstance(tool_call, dict)
                        else getattr(tool_call, "id", None)
                    )
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tool_id or "tool_call",
                            "name": function.get("name") or "tool",
                            "input": tool_input,
                        }
                    )
        target_role = "assistant" if role == "assistant" else "user"
        if converted and converted[-1]["role"] == target_role:
            converted[-1]["content"] = _as_blocks(converted[-1]["content"]) + content
        else:
            converted.append({"role": target_role, "content": content})
    for item in converted:
        blocks = item["content"]
        if len(blocks) == 1 and blocks[0].get("type") == "text":
            item["content"] = blocks[0]["text"]
    return "\n\n".join(filter(None, systems)) or None, converted


def _convert_tools(tools: list[dict]) -> list[dict]:
    result = []
    for tool in tools:
        function = tool.get("function", tool)
        result.append(
            {
                "name": function["name"],
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {"type": "object"}),
            }
        )
    return result


def _convert_tool_choice(choice: Any) -> Any:
    if choice in (None, "none"):
        return None
    if choice == "auto":
        return {"type": "auto"}
    if choice == "required":
        return {"type": "any"}
    if isinstance(choice, dict) and choice.get("type") == "function":
        return {"type": "tool", "name": choice.get("function", {}).get("name")}
    return choice


def _normalize_response(response: Any) -> SimpleNamespace:
    text, thinking, tool_calls = [], [], []
    for block in response.content:
        if block.type == "text":
            text.append(block.text)
        elif block.type == "thinking":
            thinking.append(block.thinking)
        elif block.type == "tool_use":
            tool_calls.append(
                _ns(
                    id=block.id,
                    type="function",
                    function=_ns(
                        name=block.name,
                        arguments=json.dumps(block.input, ensure_ascii=False),
                    ),
                )
            )
    finish = (
        "tool_calls" if getattr(response, "stop_reason", None) == "tool_use" else "stop"
    )
    message = _ns(
        role="assistant",
        content="".join(text),
        reasoning_content="".join(thinking) or None,
        tool_calls=tool_calls,
    )
    return _ns(choices=[_ns(message=message, finish_reason=finish)])


def _stream_chunks(stream: Any):
    try:
        for event in stream:
            event_type = getattr(event, "type", "")
            delta, finish = None, None
            if (
                event_type == "content_block_start"
                and event.content_block.type == "tool_use"
            ):
                block = event.content_block
                call = _ns(
                    index=event.index,
                    id=block.id,
                    type="function",
                    function=_ns(name=block.name, arguments=""),
                )
                delta = _ns(content=None, reasoning_content=None, tool_calls=[call])
            elif event_type == "content_block_delta":
                block = event.delta
                if block.type == "text_delta":
                    delta = _ns(
                        content=block.text, reasoning_content=None, tool_calls=[]
                    )
                elif block.type == "thinking_delta":
                    delta = _ns(
                        content=None, reasoning_content=block.thinking, tool_calls=[]
                    )
                elif block.type == "input_json_delta":
                    call = _ns(
                        index=event.index,
                        id=None,
                        type="function",
                        function=_ns(name=None, arguments=block.partial_json),
                    )
                    delta = _ns(content=None, reasoning_content=None, tool_calls=[call])
            elif event_type == "message_stop":
                delta, finish = (
                    _ns(content=None, reasoning_content=None, tool_calls=[]),
                    "stop",
                )
            if delta is not None:
                yield _ns(choices=[_ns(delta=delta, finish_reason=finish)])
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()


class _Completions:
    def __init__(self, sdk_client: Any):
        self._sdk_client = sdk_client

    def create(self, **kwargs: Any):
        request = dict(kwargs)
        system, messages = _convert_messages(request.pop("messages"))
        stream = bool(request.pop("stream", False))
        request["messages"] = messages
        if system:
            request["system"] = system
        tools = request.pop("tools", None)
        if tools:
            request["tools"] = _convert_tools(tools)
        choice = _convert_tool_choice(request.pop("tool_choice", None))
        if choice is not None:
            request["tool_choice"] = choice
        extra_body = dict(request.pop("extra_body", None) or {})
        for field in (
            "max_tokens",
            "temperature",
            "top_p",
            "top_k",
            "stop_sequences",
            "metadata",
        ):
            if field in extra_body and field not in request:
                request[field] = extra_body.pop(field)
        if extra_body:
            request["extra_body"] = extra_body
        request.setdefault("max_tokens", 1024)
        for field in (
            "frequency_penalty",
            "presence_penalty",
            "response_format",
            "seed",
        ):
            request.pop(field, None)
        response = (
            self._sdk_client.messages.create(stream=True, **request)
            if stream
            else self._sdk_client.messages.create(**request)
        )
        return _stream_chunks(response) if stream else _normalize_response(response)


class AnthropicChatClientFacade:
    def __init__(self, sdk_client: Any):
        self._sdk_client = sdk_client
        self.chat = _ns(completions=_Completions(sdk_client))

    def close(self) -> None:
        close = getattr(self._sdk_client, "close", None)
        if close:
            close()
