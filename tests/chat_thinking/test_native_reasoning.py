from app.services.chat_completion import (
    DEFAULT_THINKING_DELTA_MARKER,
    complete_llm_answer,
    encode_thinking_delta,
    stream_llm_events,
)
from app.services.llm_tool_calls import message_to_openai_dict


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

    assert message_to_openai_dict(FakeMessage()) == {
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


def test_thinking_delta_is_json_encoded_for_mixed_text_stream():
    encoded = encode_thinking_delta("分析\n下一步")

    assert encoded == f'{DEFAULT_THINKING_DELTA_MARKER}"分析\\n下一步"\n'


def test_stream_llm_events_forwards_native_reasoning_and_answer():
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

    events = list(
        stream_llm_events(
            [{"role": "user", "content": "问题"}],
            resolve_llm_config=lambda: {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "api_key": "test",
                "base_url": "https://api.deepseek.com",
                "thinking_config": {
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "high",
                },
            },
            get_llm_client=lambda config: fake_client,
        )
    )

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert events == [("thinking", "先分析"), ("answer", "最终答案")]


def test_complete_llm_answer_returns_native_reasoning():
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

    answer, thinking = complete_llm_answer(
        [{"role": "user", "content": "问题"}],
        resolve_llm_config=lambda: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "thinking_config": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        },
        get_llm_client=lambda config: fake_client,
    )

    assert captured["extra_body"]["thinking"] == {"type": "enabled"}
    assert answer == "最终答案"
    assert thinking == "先分析"
