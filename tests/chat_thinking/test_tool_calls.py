import asyncio
import json
import time

import pytest

from app.services.chat_completion import (
    complete_llm_answer_with_tools,
    prepare_llm_messages_with_tools,
)
from app.services.llm_tool_calls import parse_tool_arguments


def _llm_runtime_kwargs(fake_client, config):
    return {
        "resolve_llm_config": lambda: config,
        "get_llm_client": lambda _config: fake_client,
    }


def test_parse_tool_arguments_accepts_dict_payloads_from_compatible_apis():
    assert parse_tool_arguments({"query": "external query"}) == {
        "query": "external query"
    }


def test_parse_tool_arguments_accepts_common_search_aliases():
    assert parse_tool_arguments({"search_query": "external query"}) == {
        "query": "external query"
    }
    assert parse_tool_arguments({"keyword": "external query"}) == {
        "query": "external query"
    }
    assert parse_tool_arguments({"queries": ["first query", "second query"]}) == {
        "query": "first query second query"
    }


@pytest.mark.asyncio
async def test_prepare_llm_messages_with_tools_does_not_block_event_loop():
    class FakeMessage:
        content = "answer"
        reasoning_content = ""
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            time.sleep(0.2)
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    task = asyncio.create_task(
        prepare_llm_messages_with_tools(
            [{"role": "user", "content": "question"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_handlers={},
            **_llm_runtime_kwargs(
                fake_client,
                {
                    "provider": "test",
                    "model": "tool-model",
                    "api_key": "test",
                    "base_url": "https://example.com",
                    "thinking_config": {},
                },
            ),
        )
    )
    await asyncio.sleep(0.03)

    assert not task.done()
    result = await task
    assert result.answer == "answer"


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_executes_requested_tool():
    captured = {"calls": []}

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "外部查询"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_1"
        function = FakeToolFunction()

    class FakeMessage:
        def __init__(self, *, content="", tool_calls=None):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = tool_calls

        def model_dump(self, exclude_none=True):
            data = {"role": "assistant", "content": self.content}
            if self.tool_calls is not None:
                data["tool_calls"] = [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": FakeToolFunction.arguments,
                        },
                    }
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                assert kwargs["tool_choice"] == "auto"
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(tool_calls=[FakeToolCall()])},
                            )()
                        ]
                    },
                )()
            assert any(message["role"] == "tool" for message in kwargs["messages"])
            if "tools" in kwargs:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content="最终答案")},
                            )()
                        ]
                    },
                )()
            assert "tools" not in kwargs
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="最终答案")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_handler(arguments):
        captured["tool_arguments"] = arguments
        return {"results": [{"title": "结果"}]}

    answer, thinking, messages = await complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        **_llm_runtime_kwargs(
            fake_client,
            {
                "provider": "test",
                "model": "tool-model",
                "api_key": "test",
                "base_url": "https://example.com",
                "thinking_config": {},
            },
        ),
    )

    assert answer == "最终答案"
    assert thinking == ""
    assert captured["tool_arguments"] == {"query": "外部查询"}
    assert messages[-1]["role"] == "tool"


@pytest.mark.asyncio
async def test_tool_planning_skips_thinking_request_body():
    captured = {"calls": []}

    class FakeMessage:
        content = "answer"
        reasoning_content = ""
        tool_calls = None

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": FakeMessage()})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    await prepare_llm_messages_with_tools(
        [{"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={},
        **_llm_runtime_kwargs(
            fake_client,
            {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "api_key": "test",
                "base_url": "https://example.com",
                "thinking_config": {
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "high",
                },
            },
        ),
    )

    assert captured["calls"][0]["tools"][0]["function"]["name"] == "web_search"
    assert "extra_body" not in captured["calls"][0]


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_executes_dsml_text_tool_call():
    captured = {"calls": []}

    dsml_tool_call = (
        "<｜｜DSML｜｜tool_calls> "
        '<｜｜DSML｜｜invoke name="web_search"> '
        '<｜｜DSML｜｜parameter name="query" string="true">'
        "Blender vs CAD software difference"
        "</｜｜DSML｜｜parameter> "
        "</｜｜DSML｜｜invoke> "
        "</｜｜DSML｜｜tool_calls>"
    )

    class FakeMessage:
        def __init__(self, *, content=""):
            self.content = content
            self.reasoning_content = ""
            self.tool_calls = None

        def model_dump(self, exclude_none=True):
            return {"role": "assistant", "content": self.content}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": FakeMessage(content=dsml_tool_call)},
                            )()
                        ]
                    },
                )()
            assert any(message["role"] == "tool" for message in kwargs["messages"])
            assert dsml_tool_call not in json.dumps(
                kwargs["messages"], ensure_ascii=False
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="final answer")},
                        )()
                    ]
                },
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()

    async def fake_handler(arguments):
        captured["tool_arguments"] = arguments
        return {"results": [{"title": "result"}]}

    answer, thinking, messages = await complete_llm_answer_with_tools(
        [{"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        **_llm_runtime_kwargs(
            fake_client,
            {
                "provider": "test",
                "model": "tool-model",
                "api_key": "test",
                "base_url": "https://example.com",
                "thinking_config": {},
            },
        ),
    )

    assert answer == "final answer"
    assert thinking == ""
    assert captured["tool_arguments"] == {"query": "Blender vs CAD software difference"}
    assert messages[-1]["role"] == "tool"
