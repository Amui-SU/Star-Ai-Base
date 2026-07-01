"""Global LLM provider configuration write helpers."""

import json
from typing import Callable, Dict, Optional

from fastapi import HTTPException
from loguru import logger

from app.services.chat_config_env import _write_env_values
from app.services.chat_provider_catalog import (
    PROVIDER_ENV_FIELDS,
    _get_provider_thinking_template,
    _normalize_provider,
    _parse_thinking_config,
    _resolve_llm_config,
)


def save_global_llm_provider_config(
    *,
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    thinking_mode: str = "off",
    thinking_config: Optional[dict] = None,
    verifier: Callable[[dict], int],
    resolve_llm_config: Callable[[Optional[str]], Dict[str, str]] = _resolve_llm_config,
    get_provider_thinking_template: Callable[[str], dict] = (
        _get_provider_thinking_template
    ),
    parse_thinking_config: Callable[[object], dict] = _parse_thinking_config,
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
    reset_rag: Callable[[], None] | None = None,
    warning_logger: Callable[[str], None] = logger.warning,
    info_logger: Callable[[str], None] = logger.info,
) -> dict:
    """Validate and persist a global LLM provider configuration."""
    normalized_provider = _normalize_provider(provider)
    env_fields = PROVIDER_ENV_FIELDS.get(normalized_provider)
    if not env_fields:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型提供方: {normalized_provider}",
        )

    current = resolve_llm_config(normalized_provider)
    resolved_api_key = (api_key or "").strip() or current["api_key"]
    if not resolved_api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    normalized_thinking_mode = thinking_mode.strip().lower()
    if normalized_thinking_mode not in {"off", "standard", "custom"}:
        raise HTTPException(status_code=400, detail="不支持的思考配置模式")
    if normalized_thinking_mode == "off":
        resolved_thinking_config = {}
    elif normalized_thinking_mode == "standard":
        resolved_thinking_config = get_provider_thinking_template(normalized_provider)
        if not resolved_thinking_config:
            raise HTTPException(
                status_code=400,
                detail="该提供商没有通用标准模板，请使用自定义 JSON",
            )
    else:
        resolved_thinking_config = parse_thinking_config(thinking_config)
        if not resolved_thinking_config:
            raise HTTPException(status_code=400, detail="自定义思考配置不能为空")

    resolved_base_url = (base_url or "").strip() or current["base_url"]
    resolved_model = (model or "").strip() or current["model"]
    pending_config = {
        "provider": normalized_provider,
        "provider_label": current["provider_label"],
        "api_key": resolved_api_key,
        "base_url": resolved_base_url,
        "model": resolved_model,
        "thinking_config": resolved_thinking_config,
    }
    latency_ms = verifier(pending_config)

    env_writer(
        {
            "LLM_PROVIDER": normalized_provider,
            env_fields["api_key"]: resolved_api_key,
            env_fields["base_url"]: resolved_base_url,
            env_fields["model"]: resolved_model,
            env_fields["thinking_config"]: json.dumps(
                resolved_thinking_config,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    )

    if reset_rag is not None:
        try:
            reset_rag()
        except Exception as exc:
            warning_logger(f"重置 RAG 服务失败，将在下次重启后生效: {exc}")

    llm_config = resolve_llm_config(normalized_provider)
    info_logger(f"已保存 LLM 配置: {normalized_provider} / model={llm_config['model']}")
    return {
        "ok": True,
        "current_provider": normalized_provider,
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
        "thinking_config": llm_config["thinking_config"],
        "thinking_template": get_provider_thinking_template(normalized_provider),
        "verified": True,
        "latency_ms": latency_ms,
    }


def set_global_llm_provider(
    provider: str,
    *,
    env_writer: Callable[[Dict[str, str]], None] = _write_env_values,
    resolve_llm_config: Callable[[Optional[str]], Dict[str, str]] = _resolve_llm_config,
    info_logger: Callable[[str], None] = logger.info,
) -> dict:
    """Persist the selected global LLM provider."""
    llm_config = resolve_llm_config(provider)
    if not llm_config["api_key"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{llm_config['provider_label']} API Key 未配置，"
                "请先在 .env.local 中配置后重启后端。"
            ),
        )

    env_writer({"LLM_PROVIDER": llm_config["provider"]})
    info_logger(
        f"已切换 LLM 提供方: {llm_config['provider']} / model={llm_config['model']}"
    )
    return {
        "ok": True,
        "current_provider": llm_config["provider"],
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
    }
