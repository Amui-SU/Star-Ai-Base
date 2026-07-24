import pytest
from fastapi import HTTPException

from app.services.llm_client import get_llm_client


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
        "base_url": "https://api.anthropic.test/v1",
        "timeout": 30.0,
        "max_retries": 2,
    }


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
