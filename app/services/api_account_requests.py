"""Request option mapping for API-account-backed model calls."""

from copy import deepcopy

from app.services.api_account_config import normalize_advanced_config


def build_account_request_options(
    llm_config: dict,
    *,
    system_body: dict | None = None,
) -> dict:
    advanced = normalize_advanced_config(llm_config.get("advanced_config"))
    headers = deepcopy(advanced["headers"])
    user_agent = advanced["user_agent"].strip()
    if user_agent:
        headers["User-Agent"] = user_agent

    user_body = deepcopy(advanced["body"])
    thinking_body = normalize_advanced_config(
        {"body": llm_config.get("thinking_config") or {}}
    )["body"]

    options = {}
    if headers:
        options["extra_headers"] = headers
    if user_body or thinking_body:
        body = deepcopy(system_body or {})
        body.update(user_body)
        body.update(thinking_body)
        options["extra_body"] = body
    elif system_body:
        options.update(deepcopy(system_body))
    return options
