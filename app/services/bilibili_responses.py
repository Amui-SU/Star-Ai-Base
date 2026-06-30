"""Response parsing helpers for Bilibili API calls."""

import json
from typing import Any

import httpx


def parse_bilibili_json_response(
    response: httpx.Response, action: str
) -> dict[str, Any]:
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        snippet = (response.text or "").strip()[:200]
        raise Exception(
            f"{action}失败: B站接口返回非JSON响应 "
            f"(status={response.status_code}, body={snippet or 'EMPTY'})"
        ) from exc
