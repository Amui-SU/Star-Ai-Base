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
