from app.routers.chat import (
    THINKING_DELTA_MARKER,
    _complete_llm_answer,
    _encode_thinking_delta,
    _message_to_openai_dict,
    _stream_llm_events,
)


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
