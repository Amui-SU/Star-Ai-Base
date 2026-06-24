import asyncio
import json
import time

import pytest
from fastapi import HTTPException

from app.models import ChatRequest, KnowledgeBaseChatRequest
from app.routers.chat import (
    LLMProviderConfigRequest,
    THINKING_DELTA_MARKER,
    WebSearchConfigRequest,
    _build_thinking_completion_options,
    _complete_llm_answer_with_tools,
    _complete_llm_answer,
    _encode_thinking_delta,
    _get_provider_thinking_config,
    _get_provider_thinking_template,
    _message_to_openai_dict,
    _parse_tool_arguments,
    _parse_thinking_config,
    _prepare_llm_messages_with_tools,
    _stream_llm_events,
    get_web_search_config,
    save_llm_provider_config,
    save_web_search_config,
)


def test_chat_request_models_no_longer_expose_request_mode_switches():
    assert "smart_search" not in ChatRequest.model_fields
    assert "smart_search" not in KnowledgeBaseChatRequest.model_fields
    assert "deep_think" not in ChatRequest.model_fields
    assert "deep_think" not in KnowledgeBaseChatRequest.model_fields


def test_knowledge_base_chat_request_supports_web_search_toggle():
    assert KnowledgeBaseChatRequest(question="hello").web_search is False
    assert (
        KnowledgeBaseChatRequest(question="hello", web_search=True).web_search is True
    )


def test_knowledge_base_chat_request_supports_web_search_provider():
    assert KnowledgeBaseChatRequest(question="hello").web_search_provider == "auto"
    assert (
        KnowledgeBaseChatRequest(
            question="hello",
            web_search=True,
            web_search_provider="Tavily",
        ).web_search_provider
        == "tavily"
    )


@pytest.mark.asyncio
async def test_web_search_config_hides_tavily_key(monkeypatch):
    monkeypatch.setattr("app.routers.chat.settings.web_search_provider", "tavily")
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "tvly-secret")
    monkeypatch.setattr("app.routers.chat.settings.web_search_fallback_html", True)
    monkeypatch.setattr("app.routers.chat.settings.tavily_search_depth", "advanced")

    result = await get_web_search_config()

    assert result == {
        "provider": "tavily",
        "tavily_configured": True,
        "fallback_html": True,
        "tavily_search_depth": "advanced",
    }
    assert "tavily_api_key" not in result
    assert "api_key" not in result


@pytest.mark.asyncio
async def test_save_web_search_config_persists_tavily_key_without_echoing_it(
    monkeypatch,
):
    captured = {}
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "")
    monkeypatch.setattr(
        "app.routers.chat._write_env_values",
        lambda updates: captured.setdefault("updates", updates),
    )

    result = await save_web_search_config(
        WebSearchConfigRequest(
            provider="tavily",
            tavily_api_key="tvly-test",
            fallback_html=False,
            tavily_search_depth="advanced",
        )
    )

    assert captured["updates"] == {
        "WEB_SEARCH_PROVIDER": "tavily",
        "WEB_SEARCH_FALLBACK_HTML": "false",
        "TAVILY_SEARCH_DEPTH": "advanced",
        "TAVILY_API_KEY": "tvly-test",
    }
    assert result["provider"] == "tavily"
    assert result["tavily_configured"] is True
    assert "tavily_api_key" not in result
    assert "api_key" not in result


@pytest.mark.asyncio
async def test_save_web_search_config_requires_key_for_tavily(monkeypatch):
    monkeypatch.setattr("app.routers.chat.settings.tavily_api_key", "")

    with pytest.raises(HTTPException) as exc:
        await save_web_search_config(WebSearchConfigRequest(provider="tavily"))

    assert exc.value.status_code == 400


def test_message_to_openai_dict_keeps_only_request_safe_assistant_fields():
    class FakeMessage:
        def model_dump(self, exclude_none=True):
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": "{}"},
                    }
                ],
                "annotations": [],
                "refusal": None,
                "audio": {"id": "response-only"},
            }

    assert _message_to_openai_dict(FakeMessage()) == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "web_search", "arguments": "{}"},
            }
        ],
    }


def test_deepseek_thinking_uses_native_request_json():
    options = _build_thinking_completion_options(
        {
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
        }
    )

    assert options == {
        "extra_body": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        }
    }


def test_parse_tool_arguments_accepts_dict_payloads_from_compatible_apis():
    assert _parse_tool_arguments({"query": "external query"}) == {
        "query": "external query"
    }


def test_parse_tool_arguments_accepts_common_search_aliases():
    assert _parse_tool_arguments({"search_query": "external query"}) == {
        "query": "external query"
    }
    assert _parse_tool_arguments({"keyword": "external query"}) == {
        "query": "external query"
    }
    assert _parse_tool_arguments({"queries": ["first query", "second query"]}) == {
        "query": "first query second query"
    }


def test_dashscope_thinking_uses_enable_thinking_request_json():
    options = _build_thinking_completion_options(
        {"thinking_config": {"enable_thinking": True}}
    )

    assert options == {"extra_body": {"enable_thinking": True}}


def test_disabled_thinking_adds_no_upstream_fields():
    assert _build_thinking_completion_options({"thinking_config": {}}) == {}


def test_provider_standard_templates_are_request_body_fragments():
    assert _get_provider_thinking_template("deepseek") == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert _get_provider_thinking_template("dashscope") == {"enable_thinking": True}
    assert _get_provider_thinking_template("kimi") == {}


def test_custom_thinking_config_requires_json_object():
    assert _parse_thinking_config('{"thinking":{"type":"enabled"}}') == {
        "thinking": {"type": "enabled"}
    }
    with pytest.raises(HTTPException, match="JSON 对象"):
        _parse_thinking_config('["not", "an", "object"]')
    with pytest.raises(HTTPException, match="JSON 格式"):
        _parse_thinking_config("{bad json")


def test_provider_thinking_config_reads_persisted_json(monkeypatch):
    monkeypatch.setattr(
        "app.routers.chat.settings.deepseek_thinking_config",
        json.dumps({"thinking": {"type": "enabled"}}),
    )

    assert _get_provider_thinking_config("deepseek") == {
        "thinking": {"type": "enabled"}
    }


@pytest.mark.asyncio
async def test_save_provider_standard_thinking_verifies_then_persists(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda provider=None: {
            "provider": "deepseek",
            "provider_label": "DeepSeek",
            "api_key": "saved-key",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr(
        "app.routers.chat._verify_provider_configuration",
        lambda config: captured.setdefault("verified_config", config) and 123,
    )
    monkeypatch.setattr(
        "app.routers.chat._write_env_values",
        lambda updates: captured.setdefault("updates", updates),
    )

    result = await save_llm_provider_config(
        LLMProviderConfigRequest(
            provider="deepseek",
            thinking_mode="standard",
        )
    )

    assert captured["verified_config"]["thinking_config"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert json.loads(captured["updates"]["DEEPSEEK_THINKING_CONFIG"]) == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert result["verified"] is True
    assert result["latency_ms"] == 123


def test_thinking_delta_is_json_encoded_for_mixed_text_stream():
    encoded = _encode_thinking_delta("分析\n下一步")

    assert encoded == f'{THINKING_DELTA_MARKER}"分析\\n下一步"\n'


def test_stream_llm_events_forwards_native_reasoning_and_answer(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            reasoning_delta = type(
                "Delta",
                (),
                {"reasoning_content": "先分析", "content": None},
            )()
            answer_delta = type(
                "Delta",
                (),
                {"reasoning_content": None, "content": "最终答案"},
            )()
            return [
                type(
                    "Chunk",
                    (),
                    {"choices": [type("Choice", (), {"delta": reasoning_delta})()]},
                )(),
                type(
                    "Chunk",
                    (),
                    {"choices": [type("Choice", (), {"delta": answer_delta})()]},
                )(),
            ]

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    events = list(_stream_llm_events([{"role": "user", "content": "问题"}]))

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert events == [("thinking", "先分析"), ("answer", "最终答案")]


def test_complete_llm_answer_returns_native_reasoning(monkeypatch):
    captured = {}
    message = type(
        "Message",
        (),
        {"content": "最终答案", "reasoning_content": "先分析"},
    )()

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": message})()]},
            )()

    fake_client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()
    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking = _complete_llm_answer(
        [{"role": "user", "content": "问题"}],
    )

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert answer == "最终答案"
    assert thinking == "先分析"


@pytest.mark.asyncio
async def test_prepare_llm_messages_with_tools_does_not_block_event_loop(monkeypatch):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    task = asyncio.create_task(
        _prepare_llm_messages_with_tools(
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
        )
    )
    await asyncio.sleep(0.03)

    assert not task.done()
    result = await task
    assert result.answer == "answer"


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_executes_requested_tool(monkeypatch):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking, messages = await _complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
    )

    assert answer == "最终答案"
    assert thinking == ""
    assert captured["tool_arguments"] == {"query": "外部查询"}
    assert messages[-1]["role"] == "tool"


@pytest.mark.asyncio
async def test_tool_planning_skips_thinking_request_body(monkeypatch):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    await _prepare_llm_messages_with_tools(
        [{"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={},
    )

    assert captured["calls"][0]["tools"][0]["function"]["name"] == "web_search"
    assert "extra_body" not in captured["calls"][0]


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_executes_dsml_text_tool_call(
    monkeypatch,
):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking, messages = await _complete_llm_answer_with_tools(
        [{"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
    )

    assert answer == "final answer"
    assert thinking == ""
    assert captured["tool_arguments"] == {"query": "Blender vs CAD software difference"}
    assert messages[-1]["role"] == "tool"


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_supports_bounded_tool_rounds(
    monkeypatch,
):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking, messages = await _complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=2,
    )

    assert answer == "多轮最终答案"
    assert thinking == ""
    assert captured["queries"] == ["第一轮", "第二轮"]
    assert len([message for message in messages if message["role"] == "tool"]) == 2


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_counts_limit_exceeded_tool_calls(
    monkeypatch,
):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, _, messages = await _complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=1,
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
async def test_complete_llm_answer_with_tools_does_not_return_dsml_tool_text_after_limit(
    monkeypatch,
):
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

    monkeypatch.setattr(
        "app.routers.chat._resolve_llm_config",
        lambda: {
            "provider": "test",
            "model": "tool-model",
            "api_key": "test",
            "base_url": "https://example.com",
            "thinking_config": {},
        },
    )
    monkeypatch.setattr("app.routers.chat._get_llm_client", lambda config: fake_client)

    answer, thinking, _messages = await _complete_llm_answer_with_tools(
        [{"role": "user", "content": "问题"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        tool_handlers={"web_search": fake_handler},
        max_tool_calls=1,
    )

    assert answer == "最终答案"
    assert thinking == ""
    assert dsml_tool_call not in answer
