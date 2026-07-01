"""LLM health-check service helpers."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException


async def llm_health_response(
    db: Any,
    current_user: Any,
    *,
    resolve_llm_credentials: Callable[..., Awaitable[Any]],
    global_config_resolver: Callable[[], dict[str, Any]],
    get_llm_client: Callable[[dict[str, Any]], Any],
    warning_logger: Callable[[str], None],
    perf_counter: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    try:
        credential = await resolve_llm_credentials(
            db,
            current_user,
            global_config_resolver=global_config_resolver,
        )
        llm_config = credential.to_llm_config()
    except HTTPException as exc:
        fallback_config = global_config_resolver()
        detail = exc.detail
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        return {
            "status": "down",
            "message": message or "未配置 LLM API Key",
            "latency_ms": None,
            "model": fallback_config["model"],
            "provider": fallback_config["provider"],
        }

    start = perf_counter()
    try:
        client = get_llm_client(llm_config)
        client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        latency_ms = int((perf_counter() - start) * 1000)
        return {
            "status": "ok",
            "message": "模型服务可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }
    except Exception as exc:
        latency_ms = int((perf_counter() - start) * 1000)
        warning_logger(f"LLM 健康检查失败: {exc}")
        return {
            "status": "down",
            "message": str(exc) or "模型服务不可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }
