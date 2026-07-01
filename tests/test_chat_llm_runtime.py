import pytest

from app.services.chat_llm_runtime import (
    build_complete_llm_answer_adapter,
    build_complete_llm_answer_with_tools_adapter,
    build_prepare_llm_messages_with_tools_adapter,
    build_stream_llm_events_adapter,
)


def test_stream_llm_events_adapter_injects_runtime_dependencies():
    def stream_llm_events(
        messages, llm_config=None, *, resolve_llm_config, get_llm_client
    ):
        yield "thinking", resolve_llm_config()["model"]
        yield "answer", get_llm_client(llm_config)

    adapter = build_stream_llm_events_adapter(
        stream_llm_events=stream_llm_events,
        resolve_llm_config=lambda: {"model": "fake-model"},
        get_llm_client=lambda config: f"client:{config}",
    )

    assert list(adapter([{"role": "user", "content": "q"}], "override")) == [
        ("thinking", "fake-model"),
        ("answer", "client:override"),
    ]


def test_complete_llm_answer_adapter_injects_runtime_dependencies():
    calls = []

    def complete_llm_answer(
        messages, llm_config=None, *, resolve_llm_config, get_llm_client
    ):
        calls.append(
            (messages, llm_config, resolve_llm_config(), get_llm_client("cfg"))
        )
        return "answer", "thinking"

    adapter = build_complete_llm_answer_adapter(
        complete_llm_answer=complete_llm_answer,
        resolve_llm_config=lambda: {"model": "fake-model"},
        get_llm_client=lambda config: f"client:{config}",
    )

    assert adapter([{"role": "user", "content": "q"}], {"model": "override"}) == (
        "answer",
        "thinking",
    )
    assert calls == [
        (
            [{"role": "user", "content": "q"}],
            {"model": "override"},
            {"model": "fake-model"},
            "client:cfg",
        )
    ]


@pytest.mark.asyncio
async def test_complete_llm_answer_with_tools_adapter_injects_runtime_dependencies():
    calls = []

    async def complete_llm_answer_with_tools(
        messages,
        *,
        tools,
        tool_handlers,
        max_tool_calls,
        resolve_llm_config,
        get_llm_client,
    ):
        calls.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_handlers": tool_handlers,
                "max_tool_calls": max_tool_calls,
                "resolved": resolve_llm_config(),
                "client": get_llm_client("cfg"),
            }
        )
        return "answer", "thinking", [{"role": "tool"}]

    adapter = build_complete_llm_answer_with_tools_adapter(
        complete_llm_answer_with_tools=complete_llm_answer_with_tools,
        resolve_llm_config=lambda: {"model": "fake-model"},
        get_llm_client=lambda config: f"client:{config}",
    )

    result = await adapter(
        [{"role": "user", "content": "q"}],
        tools=[{"type": "function"}],
        tool_handlers={"web_search": object()},
        max_tool_calls=3,
    )

    assert result == ("answer", "thinking", [{"role": "tool"}])
    assert calls[0]["max_tool_calls"] == 3
    assert calls[0]["resolved"] == {"model": "fake-model"}
    assert calls[0]["client"] == "client:cfg"


@pytest.mark.asyncio
async def test_prepare_llm_messages_with_tools_adapter_injects_runtime_dependencies():
    calls = []

    async def prepare_llm_messages_with_tools(
        messages,
        *,
        tools,
        tool_handlers,
        max_tool_calls,
        after_tool_messages,
        llm_config,
        resolve_llm_config,
        get_llm_client,
    ):
        calls.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_handlers": tool_handlers,
                "max_tool_calls": max_tool_calls,
                "after_tool_messages": after_tool_messages,
                "llm_config": llm_config,
                "resolved": resolve_llm_config(),
                "client": get_llm_client("cfg"),
            }
        )
        return "tool-run"

    adapter = build_prepare_llm_messages_with_tools_adapter(
        prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
        resolve_llm_config=lambda: {"model": "fake-model"},
        get_llm_client=lambda config: f"client:{config}",
    )

    result = await adapter(
        [{"role": "user", "content": "q"}],
        tools=[{"type": "function"}],
        tool_handlers={"web_search": object()},
        max_tool_calls=3,
        after_tool_messages=lambda messages: messages,
        llm_config={"model": "override"},
    )

    assert result == "tool-run"
    assert calls[0]["max_tool_calls"] == 3
    assert calls[0]["llm_config"] == {"model": "override"}
    assert calls[0]["resolved"] == {"model": "fake-model"}
    assert calls[0]["client"] == "client:cfg"
