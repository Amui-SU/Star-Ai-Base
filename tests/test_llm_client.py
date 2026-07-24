import anthropic
import httpx
import pytest
from fastapi import HTTPException

from app.services.llm_client import get_llm_client, normalize_anthropic_base_url


def test_get_llm_client_uses_resolved_config_and_client_factory():
    captured = {}

    def fake_factory(**kwargs):
        captured.update(kwargs)
        return "client"

    client = get_llm_client(
        resolve_llm_config=lambda: {
            "api_key": "secret-key",
            "base_url": "https://llm.example/v1",
        },
        client_factory=fake_factory,
    )

    assert client == "client"
    assert captured == {
        "api_key": "secret-key",
        "base_url": "https://llm.example/v1",
        "timeout": 30.0,
        "max_retries": 2,
    }


def test_get_llm_client_rejects_missing_api_key_before_creating_client():
    called = False

    def fake_factory(**kwargs):
        nonlocal called
        called = True

    with pytest.raises(HTTPException) as exc_info:
        get_llm_client(
            {"api_key": "", "base_url": "https://llm.example/v1"},
            client_factory=fake_factory,
        )

    assert exc_info.value.status_code == 400
    assert not called


def test_get_llm_client_uses_anthropic_facade_factory_for_anthropic_protocol():
    captured = {}

    def fake_anthropic_factory(**kwargs):
        captured.update(kwargs)
        return "anthropic-sdk"

    client = get_llm_client(
        {
            "provider": "claude",
            "protocol": "anthropic_messages",
            "api_key": "secret-key",
            "base_url": "https://api.anthropic.test/v1",
        },
        anthropic_client_factory=fake_anthropic_factory,
        anthropic_facade_factory=lambda sdk: ("facade", sdk),
    )

    assert client == ("facade", "anthropic-sdk")
    assert captured == {
        "api_key": "secret-key",
        "base_url": "https://api.anthropic.test",
        "timeout": 30.0,
        "max_retries": 2,
    }


@pytest.mark.parametrize(
    ("configured_url", "normalized_url"),
    [
        ("https://api.anthropic.com/v1", "https://api.anthropic.com"),
        ("https://api.anthropic.com/v1/", "https://api.anthropic.com"),
        ("https://proxy.example/anthropic/v1", "https://proxy.example/anthropic"),
        ("https://proxy.example", "https://proxy.example"),
        ("https://proxy.example/anthropic", "https://proxy.example/anthropic"),
        (
            "https://proxy.example/anthropic/v1/?tenant=alpha",
            "https://proxy.example/anthropic?tenant=alpha",
        ),
    ],
)
def test_normalize_anthropic_base_url_only_removes_final_v1_segment(
    configured_url, normalized_url
):
    assert normalize_anthropic_base_url(configured_url) == normalized_url


@pytest.mark.parametrize(
    ("configured_url", "expected_request_url"),
    [
        ("https://api.anthropic.com/v1", "https://api.anthropic.com/v1/messages"),
        (
            "https://proxy.example/anthropic/v1",
            "https://proxy.example/anthropic/v1/messages",
        ),
        ("https://proxy.example", "https://proxy.example/v1/messages"),
    ],
)
def test_real_anthropic_sdk_prepares_exact_messages_url(
    configured_url, expected_request_url
):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
                "model": "claude-test",
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    sdk_client = anthropic.Anthropic(
        api_key="test-key",
        base_url=normalize_anthropic_base_url(configured_url),
        http_client=http_client,
    )
    try:
        sdk_client.messages.create(
            model="claude-test",
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
    finally:
        sdk_client.close()

    assert captured["url"] == expected_request_url
    assert "/v1/v1/" not in captured["url"]


@pytest.mark.parametrize("protocol", [None, "openai_compatible"])
def test_get_llm_client_keeps_openai_factory_path(protocol):
    calls = []
    result = get_llm_client(
        {
            "protocol": protocol,
            "api_key": "secret",
            "base_url": "https://openai.test/v1",
        },
        client_factory=lambda **kwargs: calls.append(kwargs) or "openai",
        anthropic_client_factory=lambda **_kwargs: pytest.fail("wrong factory"),
    )
    assert result == "openai"
    assert len(calls) == 1


@pytest.mark.parametrize("provider", ["tavily", None])
def test_get_llm_client_rejects_non_llm_provider(provider):
    with pytest.raises(HTTPException) as exc_info:
        get_llm_client(
            {
                "provider": provider,
                "protocol": None,
                "api_key": "secret",
                "base_url": "https://search.test",
            }
        )
    assert exc_info.value.status_code == 400
