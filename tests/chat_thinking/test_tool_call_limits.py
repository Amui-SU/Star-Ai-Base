import json

import pytest

from app.services.chat_completion import complete_llm_answer_with_tools

_LLM_RUNTIME_CONFIG = {
    "provider": "test",
    "model": "tool-model",
    "api_key": "test",
    "base_url": "https://example.com",
    "thinking_config": {},
}


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_supports_bounded_tool_rounds():
    captured = {"queries": [], "calls": []}

    class FakeToolFunction:
        def __init__(self, query: str):
            self.name = "web_search"
            self.arguments = json.dumps({"query": query}, ensure_ascii=False)

    class FakeToolCall:
        def __init__(self, call_id: str, query: str):
            self.id = call_id
            self.function = FakeToolFunction(query)

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
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in self.tool_calls
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            call_number = len(captured["calls"])
            if call_number == 1:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[FakeToolCall("call_1", "第一轮")]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            if call_number == 2:
                assert kwargs["tools"][0]["function"]["name"] == "web_search"
                assert (
                    len(
                        [
                            message
                            for message in kwargs["messages"]
                            if message["role"] == "tool"
                        ]
                    )
                    == 1
                )
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[FakeToolCall("call_2", "第二轮")]
                                    )
                                },
                            )()
                        ]
                    },
                )()
            assert "tools" not in kwargs
            assert (
                len(
                    [
                        message
                        for message in kwargs["messages"]
                        if message["role"] == "tool"
                    ]
                )
                == 2
            )
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": FakeMessage(content="多轮最终答案")},
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
        captured["queries"].append(arguments["query"])
        return {"results": [{"title": arguments["query"]}]}

    answer, thinking, messages = await complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=2,
        resolve_llm_config=lambda: _LLM_RUNTIME_CONFIG,
        get_llm_client=lambda _config: fake_client,
    )

    assert answer == "多轮最终答案"
    assert thinking == ""
    assert captured["queries"] == ["第一轮", "第二轮"]
    assert len([message for message in messages if message["role"] == "tool"]) == 2


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_counts_limit_exceeded_tool_calls():
    captured = {"queries": [], "calls": []}

    class FakeToolFunction:
        def __init__(self, query: str):
            self.name = "web_search"
            self.arguments = json.dumps({"query": query}, ensure_ascii=False)

    class FakeToolCall:
        def __init__(self, call_id: str, query: str):
            self.id = call_id
            self.function = FakeToolFunction(query)

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
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in self.tool_calls
                ]
            return data

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"].append(kwargs)
            if len(captured["calls"]) == 1:
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": FakeMessage(
                                        tool_calls=[
                                            FakeToolCall("call_1", "执行"),
                                            FakeToolCall("call_2", "超额"),
                                        ]
                                    )
                                },
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
                            "Choice", (), {"message": FakeMessage(content="最终答案")}
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
        captured["queries"].append(arguments["query"])
        return {"results": [{"title": arguments["query"]}]}

    answer, _, messages = await complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=1,
        resolve_llm_config=lambda: _LLM_RUNTIME_CONFIG,
        get_llm_client=lambda _config: fake_client,
    )

    tool_messages = [message for message in messages if message["role"] == "tool"]
    assert answer == "最终答案"
    assert captured["queries"] == ["执行"]
    assert len(captured["calls"]) == 2
    assert len(tool_messages) == 2
    assert json.loads(tool_messages[-1]["content"])["error"] == (
        "tool_call_limit_exceeded"
    )


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_does_not_return_dsml_tool_text_after_limit():
    captured = {"calls": []}
    dsml_tool_call = (
        "<｜｜DSML｜｜tool_calls>"
        '<｜｜DSML｜｜invoke name="fetch_web_page">'
        '<｜｜DSML｜｜parameter name="url" string="true">'
        "https://example.com/article"
        "</｜｜DSML｜｜parameter>"
        "</｜｜DSML｜｜invoke>"
        "</｜｜DSML｜｜tool_calls>"
    )

    class FakeToolFunction:
        name = "web_search"
        arguments = json.dumps({"query": "外部查询"}, ensure_ascii=False)

    class FakeToolCall:
        id = "call_search"
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
                        "id": "call_search",
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
            if len(captured["calls"]) == 2:
                assert "tools" not in kwargs
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
            assert "tools" not in kwargs
            serialized = json.dumps(kwargs["messages"], ensure_ascii=False)
            assert "不要再输出工具调用" in serialized
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice", (), {"message": FakeMessage(content="最终答案")}
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
        return {"results": [{"title": "result"}]}

    answer, thinking, _messages = await complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=1,
        resolve_llm_config=lambda: _LLM_RUNTIME_CONFIG,
        get_llm_client=lambda _config: fake_client,
    )

    assert answer == "最终答案"
    assert thinking == ""
    assert dsml_tool_call not in answer
