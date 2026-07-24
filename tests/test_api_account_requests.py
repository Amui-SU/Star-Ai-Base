from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.services.api_account_requests import build_account_request_options


def test_build_account_request_options_merges_headers_body_and_thinking():
    config = {
        "model": "real-model",
        "advanced_config": {
            "user_agent": "WorkspaceClient/1.0",
            "headers": {"X-Tenant": "alpha"},
            "body": {"temperature": 0.8, "reasoning_effort": "low"},
        },
        "thinking_config": {"reasoning_effort": "high"},
    }
    original = deepcopy(config)

    options = build_account_request_options(
        config,
        system_body={"temperature": 0.5, "max_tokens": 16},
    )

    assert options == {
        "extra_headers": {
            "X-Tenant": "alpha",
            "User-Agent": "WorkspaceClient/1.0",
        },
        "extra_body": {
            "temperature": 0.8,
            "max_tokens": 16,
            "reasoning_effort": "high",
        },
    }
    assert config == original


def test_build_account_request_options_returns_empty_without_configuration():
    assert build_account_request_options({}) == {}


@pytest.mark.parametrize("field", ["model", "messages", "tools", "stream"])
def test_build_account_request_options_rejects_system_core_body_fields(field):
    with pytest.raises(HTTPException, match=f"body.{field}"):
        build_account_request_options(
            {"advanced_config": {"body": {field: "override"}}}
        )


def test_build_account_request_options_rejects_core_fields_from_thinking_config():
    with pytest.raises(HTTPException, match="body.model"):
        build_account_request_options({"thinking_config": {"model": "override"}})
