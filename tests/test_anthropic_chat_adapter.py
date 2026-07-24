import json
from types import SimpleNamespace

from app.services.anthropic_chat_adapter import AnthropicChatClientFacade


def ns(**kwargs):
    return SimpleNamespace(**kwargs)


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def facade(response):
    messages = FakeMessages(response)
    return AnthropicChatClientFacade(ns(messages=messages)), messages


def test_converts_system_messages_options_and_text_response():
    client, sdk = facade(
        ns(content=[ns(type="text", text="Hello")], stop_reason="end_turn")
    )

    result = client.chat.completions.create(
        model="claude-test",
        messages=[
            {"role": "system", "content": "Be precise"},
            {"role": "user", "content": "Hi"},
        ],
        temperature=0.2,
        extra_headers={"X-Tenant": "alpha"},
        extra_body={"top_p": 0.8},
    )

    assert sdk.calls == [
        {
            "model": "claude-test",
            "system": "Be precise",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1024,
            "temperature": 0.2,
            "top_p": 0.8,
            "extra_headers": {"X-Tenant": "alpha"},
        }
    ]
    assert result.choices[0].message.content == "Hello"
    assert result.choices[0].message.tool_calls == []


def test_converts_tools_results_and_normalizes_thinking_and_tool_use():
    client, sdk = facade(
        ns(
            content=[
                ns(type="thinking", thinking="Plan"),
                ns(type="text", text="Calling"),
                ns(type="tool_use", id="toolu_1", name="lookup", input={"q": "x"}),
            ],
            stop_reason="tool_use",
        )
    )
    result = client.chat.completions.create(
        model="claude-test",
        messages=[
            {"role": "user", "content": "Find x"},
            {
                "role": "assistant",
                "content": "I will search",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"q":"x"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": '{"ok":true}'},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Search",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "lookup"}},
    )

    call = sdk.calls[0]
    assert call["tools"] == [
        {"name": "lookup", "description": "Search", "input_schema": {"type": "object"}}
    ]
    assert call["tool_choice"] == {"type": "tool", "name": "lookup"}
    assert call["messages"][1]["content"][1] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "lookup",
        "input": {"q": "x"},
    }
    assert call["messages"][2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": '{"ok":true}'}
        ],
    }
    message = result.choices[0].message
    assert message.content == "Calling"
    assert message.reasoning_content == "Plan"
    assert message.tool_calls[0].id == "toolu_1"
    assert json.loads(message.tool_calls[0].function.arguments) == {"q": "x"}


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def __iter__(self):
        return iter(self.events)

    def close(self):
        self.closed = True


def test_stream_normalizes_text_thinking_and_tool_json_and_closes():
    stream = FakeStream(
        [
            ns(
                type="content_block_start",
                index=0,
                content_block=ns(type="tool_use", id="toolu_9", name="lookup"),
            ),
            ns(
                type="content_block_delta",
                index=0,
                delta=ns(type="input_json_delta", partial_json='{"q":'),
            ),
            ns(
                type="content_block_delta",
                index=0,
                delta=ns(type="input_json_delta", partial_json='"x"}'),
            ),
            ns(
                type="content_block_delta",
                index=1,
                delta=ns(type="thinking_delta", thinking="Plan"),
            ),
            ns(
                type="content_block_delta",
                index=2,
                delta=ns(type="text_delta", text="Done"),
            ),
            ns(type="message_stop"),
        ]
    )
    client, _sdk = facade(stream)

    chunks = list(
        client.chat.completions.create(
            model="claude-test",
            messages=[{"role": "user", "content": "Hi"}],
            stream=True,
        )
    )

    assert chunks[0].choices[0].delta.tool_calls[0].function.name == "lookup"
    assert chunks[1].choices[0].delta.tool_calls[0].function.arguments == '{"q":'
    assert chunks[3].choices[0].delta.reasoning_content == "Plan"
    assert chunks[4].choices[0].delta.content == "Done"
    assert chunks[-1].choices[0].finish_reason == "stop"
    assert stream.closed is True
