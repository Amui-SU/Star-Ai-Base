"""
Bilibili RAG 知识库系统
对话路由 - 智能问答
"""

import re
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI, APIConnectionError, APITimeoutError
from langchain.schema import Document
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    ChatRequest,
    ChatResponse,
    FavoriteFolder,
    FavoriteVideo,
    VideoCache,
)
from app.config import settings
from app.routers.knowledge import get_rag_service

router = APIRouter(prefix="/chat", tags=["对话"])
LEGACY_SCOPED_API_DETAIL = "旧全局接口已禁用，请使用 /knowledge-bases/* 范围化 API。"


def _raise_legacy_scoped_api_required() -> None:
    raise HTTPException(status_code=410, detail=LEGACY_SCOPED_API_DETAIL)


PROVIDER_META = {
    "dashscope": {
        "label": "阿里云 DashScope",
        "api_key": lambda: settings.openai_api_key,
        "base_url": lambda: settings.openai_base_url,
        "model": lambda: settings.llm_model,
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_key": lambda: settings.deepseek_api_key,
        "base_url": lambda: settings.deepseek_base_url,
        "model": lambda: settings.deepseek_model,
    },
    "openai": {
        "label": "OpenAI",
        "api_key": lambda: settings.openai_native_api_key,
        "base_url": lambda: settings.openai_native_base_url,
        "model": lambda: settings.openai_native_model,
    },
    "kimi": {
        "label": "Moonshot Kimi",
        "api_key": lambda: settings.kimi_api_key,
        "base_url": lambda: settings.kimi_base_url,
        "model": lambda: settings.kimi_model,
    },
    "siliconflow": {
        "label": "SiliconFlow",
        "api_key": lambda: settings.siliconflow_api_key,
        "base_url": lambda: settings.siliconflow_base_url,
        "model": lambda: settings.siliconflow_model,
    },
    "zhipu": {
        "label": "智谱 GLM",
        "api_key": lambda: settings.zhipu_api_key,
        "base_url": lambda: settings.zhipu_base_url,
        "model": lambda: settings.zhipu_model,
    },
}
SUPPORTED_LLM_PROVIDERS = set(PROVIDER_META.keys())
_current_llm_provider = (
    settings.llm_provider
    if settings.llm_provider in SUPPORTED_LLM_PROVIDERS
    else "dashscope"
)
THINKING_DELTA_MARKER = "[[THINKING_DELTA]]"


@dataclass
class LLMToolRunResult:
    messages: list[dict]
    answer: str | None = None
    thinking: str = ""


class LLMProviderUpdateRequest(BaseModel):
    provider: str


class LLMProviderConfigRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    thinking_mode: str = "off"
    thinking_config: Optional[dict] = None


PROVIDER_ENV_FIELDS = {
    "dashscope": {
        "api_key": "DASHSCOPE_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "model": "LLM_MODEL",
        "thinking_config": "DASHSCOPE_THINKING_CONFIG",
    },
    "deepseek": {
        "api_key": "DEEPSEEK_API_KEY",
        "base_url": "DEEPSEEK_BASE_URL",
        "model": "DEEPSEEK_MODEL",
        "thinking_config": "DEEPSEEK_THINKING_CONFIG",
    },
    "openai": {
        "api_key": "OPENAI_NATIVE_API_KEY",
        "base_url": "OPENAI_NATIVE_BASE_URL",
        "model": "OPENAI_NATIVE_MODEL",
        "thinking_config": "OPENAI_NATIVE_THINKING_CONFIG",
    },
    "kimi": {
        "api_key": "KIMI_API_KEY",
        "base_url": "KIMI_BASE_URL",
        "model": "KIMI_MODEL",
        "thinking_config": "KIMI_THINKING_CONFIG",
    },
    "siliconflow": {
        "api_key": "SILICONFLOW_API_KEY",
        "base_url": "SILICONFLOW_BASE_URL",
        "model": "SILICONFLOW_MODEL",
        "thinking_config": "SILICONFLOW_THINKING_CONFIG",
    },
    "zhipu": {
        "api_key": "ZHIPU_API_KEY",
        "base_url": "ZHIPU_BASE_URL",
        "model": "ZHIPU_MODEL",
        "thinking_config": "ZHIPU_THINKING_CONFIG",
    },
}


SETTINGS_FIELD_BY_ENV = {
    "LLM_PROVIDER": "llm_provider",
    "DASHSCOPE_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "LLM_MODEL": "llm_model",
    "DASHSCOPE_THINKING_CONFIG": "dashscope_thinking_config",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "DEEPSEEK_MODEL": "deepseek_model",
    "DEEPSEEK_THINKING_CONFIG": "deepseek_thinking_config",
    "OPENAI_NATIVE_API_KEY": "openai_native_api_key",
    "OPENAI_NATIVE_BASE_URL": "openai_native_base_url",
    "OPENAI_NATIVE_MODEL": "openai_native_model",
    "OPENAI_NATIVE_THINKING_CONFIG": "openai_native_thinking_config",
    "KIMI_API_KEY": "kimi_api_key",
    "KIMI_BASE_URL": "kimi_base_url",
    "KIMI_MODEL": "kimi_model",
    "KIMI_THINKING_CONFIG": "kimi_thinking_config",
    "SILICONFLOW_API_KEY": "siliconflow_api_key",
    "SILICONFLOW_BASE_URL": "siliconflow_base_url",
    "SILICONFLOW_MODEL": "siliconflow_model",
    "SILICONFLOW_THINKING_CONFIG": "siliconflow_thinking_config",
    "ZHIPU_API_KEY": "zhipu_api_key",
    "ZHIPU_BASE_URL": "zhipu_base_url",
    "ZHIPU_MODEL": "zhipu_model",
    "ZHIPU_THINKING_CONFIG": "zhipu_thinking_config",
}

PROVIDER_THINKING_SETTINGS_FIELDS = {
    "dashscope": "dashscope_thinking_config",
    "deepseek": "deepseek_thinking_config",
    "openai": "openai_native_thinking_config",
    "kimi": "kimi_thinking_config",
    "siliconflow": "siliconflow_thinking_config",
    "zhipu": "zhipu_thinking_config",
}

PROVIDER_THINKING_TEMPLATES = {
    "dashscope": {"enable_thinking": True},
    "deepseek": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "openai": {"reasoning_effort": "medium"},
    "kimi": {},
    "siliconflow": {"enable_thinking": True},
    "zhipu": {"thinking": {"type": "enabled"}},
}


def _normalize_provider(provider: Optional[str]) -> str:
    if not provider:
        return _current_llm_provider
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_LLM_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {provider}")
    return normalized


def _resolve_llm_config(provider: Optional[str] = None) -> Dict[str, str]:
    normalized = _normalize_provider(provider)
    meta = PROVIDER_META.get(normalized)
    if not meta:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {normalized}")
    return {
        "provider": normalized,
        "provider_label": meta["label"],
        "api_key": meta["api_key"](),
        "base_url": meta["base_url"](),
        "model": meta["model"](),
        "thinking_config": _get_provider_thinking_config(normalized),
    }


def _get_provider_thinking_template(provider: str) -> dict:
    return dict(PROVIDER_THINKING_TEMPLATES.get(provider, {}))


def _parse_thinking_config(raw_config) -> dict:
    if raw_config in (None, ""):
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    try:
        parsed = json.loads(str(raw_config))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="思考配置 JSON 格式错误") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="思考配置必须是 JSON 对象")
    return parsed


def _get_provider_thinking_config(provider: str) -> dict:
    field = PROVIDER_THINKING_SETTINGS_FIELDS.get(provider)
    if not field:
        return {}
    return _parse_thinking_config(getattr(settings, field, ""))


def _env_file_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env.local"


def _read_env_values(path: Path) -> tuple[list[str], Dict[str, str]]:
    if not path.exists():
        return [], {}

    lines = path.read_text(encoding="utf-8").splitlines()
    values: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return lines, values


def _write_env_values(updates: Dict[str, str]) -> None:
    path = _env_file_path()
    lines, existing = _read_env_values(path)
    written = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            next_lines.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            next_lines.append(line)

    missing = [key for key in updates if key not in written and key not in existing]
    if missing and next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key in missing:
        next_lines.append(f"{key}={updates[key]}")

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in updates.items():
        field = SETTINGS_FIELD_BY_ENV.get(key)
        if field:
            setattr(settings, field, value)


@router.get("/llm/config")
async def get_llm_config(_current_user=Depends(get_current_user)):
    """获取当前模型配置（不返回密钥）"""
    current = _resolve_llm_config()
    providers = []
    for provider, meta in PROVIDER_META.items():
        providers.append(
            {
                "provider": provider,
                "label": meta["label"],
                "enabled": bool(meta["api_key"]()),
                "model": meta["model"](),
                "base_url": meta["base_url"](),
                "thinking_config": _get_provider_thinking_config(provider),
                "thinking_template": _get_provider_thinking_template(provider),
            }
        )
    return {
        "current_provider": current["provider"],
        "providers": providers,
    }


@router.post("/llm/provider-config")
async def save_llm_provider_config(
    body: LLMProviderConfigRequest,
    _current_user=Depends(get_current_user),
):
    """验证并保存模型提供方配置到 .env.local。"""
    global _current_llm_provider

    provider = _normalize_provider(body.provider)
    env_fields = PROVIDER_ENV_FIELDS.get(provider)
    if not env_fields:
        raise HTTPException(status_code=400, detail=f"不支持的模型提供方: {provider}")

    current = _resolve_llm_config(provider)
    api_key = (body.api_key or "").strip() or current["api_key"]
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    thinking_mode = body.thinking_mode.strip().lower()
    if thinking_mode not in {"off", "standard", "custom"}:
        raise HTTPException(status_code=400, detail="不支持的思考配置模式")
    if thinking_mode == "off":
        thinking_config = {}
    elif thinking_mode == "standard":
        thinking_config = _get_provider_thinking_template(provider)
        if not thinking_config:
            raise HTTPException(
                status_code=400,
                detail="该提供商没有通用标准模板，请使用自定义 JSON",
            )
    else:
        thinking_config = _parse_thinking_config(body.thinking_config)
        if not thinking_config:
            raise HTTPException(status_code=400, detail="自定义思考配置不能为空")

    base_url = (body.base_url or "").strip() or current["base_url"]
    model = (body.model or "").strip() or current["model"]
    pending_config = {
        "provider": provider,
        "provider_label": current["provider_label"],
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "thinking_config": thinking_config,
    }
    latency_ms = _verify_provider_configuration(pending_config)

    updates = {
        "LLM_PROVIDER": provider,
        env_fields["api_key"]: api_key,
        env_fields["base_url"]: base_url,
        env_fields["model"]: model,
        env_fields["thinking_config"]: json.dumps(
            thinking_config,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }

    _write_env_values(updates)
    _current_llm_provider = provider

    try:
        from app.routers import knowledge

        knowledge._rag_service = None
    except Exception as e:
        logger.warning(f"重置 RAG 服务失败，将在下次重启后生效: {e}")

    llm_config = _resolve_llm_config(provider)
    logger.info(f"已保存 LLM 配置: {provider} / model={llm_config['model']}")
    return {
        "ok": True,
        "current_provider": provider,
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
        "thinking_config": llm_config["thinking_config"],
        "thinking_template": _get_provider_thinking_template(provider),
        "verified": True,
        "latency_ms": latency_ms,
    }


@router.post("/llm/config")
async def set_llm_config(
    body: LLMProviderUpdateRequest,
    _current_user=Depends(get_current_user),
):
    """切换当前问答模型提供方"""
    global _current_llm_provider
    llm_config = _resolve_llm_config(body.provider)
    if not llm_config["api_key"]:
        raise HTTPException(
            status_code=400,
            detail=f"{llm_config['provider_label']} API Key 未配置，请先在 .env 中配置后重启后端。",
        )
    _current_llm_provider = llm_config["provider"]
    logger.info(
        f"已切换 LLM 提供方: {_current_llm_provider} / model={llm_config['model']}"
    )
    return {
        "ok": True,
        "current_provider": _current_llm_provider,
        "model": llm_config["model"],
        "provider_label": llm_config["provider_label"],
    }


@router.get("/health/llm")
async def llm_health_check(_current_user=Depends(get_current_user)):
    """LLM 连通性检查"""
    llm_config = _resolve_llm_config()
    if not llm_config["api_key"]:
        return {
            "status": "down",
            "message": "未配置 LLM API Key",
            "latency_ms": None,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }

    start = time.perf_counter()
    try:
        client = _get_llm_client(llm_config)
        # 最小化探活请求，避免额外开销
        client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "status": "ok",
            "message": "模型服务可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(f"LLM 健康检查失败: {e}")
        return {
            "status": "down",
            "message": str(e) or "模型服务不可用",
            "latency_ms": latency_ms,
            "model": llm_config["model"],
            "provider": llm_config["provider"],
        }


def _get_llm_client(llm_config: Optional[Dict[str, str]] = None) -> OpenAI:
    """获取 LLM 客户端"""
    cfg = llm_config or _resolve_llm_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 LLM API Key")
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=30.0,
        max_retries=2,
    )


def _is_llm_connection_error(err: Exception) -> bool:
    """判断是否为上游模型连接/超时问题"""
    if isinstance(err, (APIConnectionError, APITimeoutError)):
        return True
    text = str(err).lower()
    return "connection error" in text or "timed out" in text or "timeout" in text


def _build_llm_unavailable_answer() -> str:
    """模型不可用时的用户可读兜底回答"""
    return (
        "当前 AI 模型服务连接不稳定，暂时无法生成回答。\n\n"
        "你可以先尝试：\n"
        "1. 稍后重试提问；\n"
        "2. 检查后端网络与模型服务配置（API Key / Base URL）；\n"
        "3. 先在左侧完成收藏夹入库，稍后再问。"
    )


def _build_overview_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个收藏夹知识库助手。用户想要了解他们收藏夹的整体内容。\n"
        "请根据以下视频信息回答用户的问题。回答要：\n"
        "1. 自然、友好、有条理\n"
        "2. 可以总结、分类、提炼要点\n"
        "3. 如果内容较多，挑选代表性的进行介绍\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _build_rag_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个知识库助手，基于用户收藏的视频内容回答问题。\n"
        "请根据以下检索到的视频内容回答：\n"
        "1. 直接回答问题，引用相关内容\n"
        "2. 回答要自然、有条理\n"
        "3. 可以引用视频标题作为来源\n\n"
        f"相关内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _build_fallback_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户的问题在现有知识库中没有检索到直接内容。\n"
        "以下是用户收藏夹中的视频概览（如果为空说明用户还没入库）：\n"
        f"{context}\n\n"
        "请根据以上信息（如果有）：\n"
        "1. 尝试回答用户问题\n"
        "2. 如果没有任何视频信息，礼貌地告诉用户需要先在左侧选择收藏夹并点击「入库」或者「更新」\n"
        '3. 保持像真人助手一样的语气，不要显示这是"备选方案"'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _build_direct_messages(question: str) -> list[dict]:
    """通用回答（不查库）"""
    system = (
        "你是一个知识库问答助手。\n" "请直接回答用户问题，避免引入收藏夹或知识库内容。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _build_direct_messages_with_context(context: str, question: str) -> list[dict]:
    """带收藏夹上下文的通用回答（引导用户提问）"""
    system = (
        "你是一个知识库问答助手。\n"
        "以下是用户收藏夹的概览（收藏夹名称与视频标题）：\n"
        f"{context}\n\n"
        "请先回答用户问题，再根据收藏夹内容引导用户提出与收藏相关的问题。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _log_final_payload(route: str, messages: list[dict], sources: list[dict]) -> None:
    """记录最终发送给 LLM 的内容与来源"""
    logger.info(f"最终路由: {route}")
    logger.info(f"最终消息: {messages}")
    logger.info(f"最终来源数量: {len(sources)}")


def _enforce_markdown_output(messages: list[dict]) -> list[dict]:
    """统一要求模型输出 Markdown，便于前端结构化渲染。"""
    if not messages:
        return messages

    markdown_instruction = (
        "输出要求：必须使用 Markdown 格式回答，并严格遵守以下规则：\n"
        "1) 先给一个二级标题（例如：## 回答要点）；\n"
        "2) 要点必须使用短横线或数字列表；\n"
        "3) 关键信息必须用 **加粗**；\n"
        "4) 补充说明必须至少包含一个 > 引用块；\n"
        "5) 代码必须使用带语言标识的三反引号代码块；\n"
        "6) 需要对比时使用 Markdown 表格；\n"
        "7) 禁止输出 HTML 标签。\n\n"
        "示例结构（仅示例，内容按用户问题生成）：\n"
        "## 回答要点\n"
        "- **重点1**：xxx\n"
        "- **重点2**：xxx\n\n"
        "> 补充说明：xxx"
    )

    normalized_messages = [dict(message) for message in messages]
    first = normalized_messages[0]
    if first.get("role") == "system":
        content = str(first.get("content") or "")
        if "Markdown" not in content and "markdown" not in content:
            first["content"] = f"{content}\n\n{markdown_instruction}"
    else:
        normalized_messages.insert(
            0, {"role": "system", "content": markdown_instruction}
        )
    return normalized_messages


def _apply_mode_instructions(
    messages: list[dict], thinking_enabled: bool
) -> list[dict]:
    """根据当前模型配置补充思考模式指令。"""
    if not thinking_enabled:
        return messages

    mode_instruction = (
        "已开启深度思考模式。请使用模型原生 reasoning/thinking 通道进行推理，"
        "最终回答保持清晰简洁；不要在正文中伪造或重复思考过程。"
    )
    normalized = [dict(message) for message in messages]
    first = normalized[0] if normalized else None
    if first and first.get("role") == "system":
        first["content"] = f"{first.get('content')}\n\n{mode_instruction}"
    else:
        normalized.insert(0, {"role": "system", "content": mode_instruction})
    return normalized


def _build_thinking_completion_options(llm_config: dict) -> dict:
    """把已保存的请求体 JSON 注入 OpenAI 兼容客户端。"""
    thinking_config = llm_config.get("thinking_config") or {}
    if not thinking_config:
        return {}
    return {"extra_body": thinking_config}


def _verify_provider_configuration(llm_config: dict) -> int:
    start = time.perf_counter()
    client = _get_llm_client(llm_config)
    try:
        client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "请只回复 OK"}],
            max_tokens=16,
            stream=False,
            **_build_thinking_completion_options(llm_config),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"模型配置验证失败: {str(exc)}",
        ) from exc
    return int((time.perf_counter() - start) * 1000)


def _encode_thinking_delta(content: str) -> str:
    return f"{THINKING_DELTA_MARKER}{json.dumps(content, ensure_ascii=False)}\n"


def _stream_llm_events(messages: list[dict]):
    """Yield native thinking and answer deltas from the configured model."""
    llm_config = _resolve_llm_config()
    client = _get_llm_client(llm_config)
    stream = client.chat.completions.create(
        model=llm_config["model"],
        messages=messages,
        temperature=0.5,
        stream=True,
        **_build_thinking_completion_options(llm_config),
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning_piece = getattr(delta, "reasoning_content", None)
        if reasoning_piece:
            yield "thinking", reasoning_piece
        if delta and delta.content:
            yield "answer", delta.content


def _complete_llm_answer(
    messages: list[dict],
) -> tuple[str, str]:
    llm_config = _resolve_llm_config()
    client = _get_llm_client(llm_config)
    response = client.chat.completions.create(
        model=llm_config["model"],
        messages=messages,
        temperature=0.5,
        **_build_thinking_completion_options(llm_config),
    )
    message = response.choices[0].message
    thinking, answer = _extract_thinking_and_answer(
        message.content or "",
        getattr(message, "reasoning_content", None),
    )
    return answer, thinking


def _message_to_openai_dict(message: Any) -> dict:
    if isinstance(message, dict):
        raw = message
    elif hasattr(message, "model_dump"):
        raw = message.model_dump(exclude_none=True)
    elif hasattr(message, "dict"):
        raw = message.dict(exclude_none=True)
    else:
        raw = {"role": "assistant", "content": getattr(message, "content", "") or ""}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            raw["tool_calls"] = [
                _tool_call_to_dict(tool_call) for tool_call in tool_calls
            ]

    result = {
        "role": raw.get("role") or "assistant",
        "content": raw.get("content") or "",
    }
    if raw.get("tool_calls"):
        result["tool_calls"] = raw["tool_calls"]
    return result


def _tool_call_to_dict(tool_call: Any) -> dict:
    if isinstance(tool_call, dict):
        return tool_call
    function = getattr(tool_call, "function", None)
    return {
        "id": getattr(tool_call, "id", ""),
        "type": getattr(tool_call, "type", "function"),
        "function": {
            "name": getattr(function, "name", ""),
            "arguments": getattr(function, "arguments", "{}"),
        },
    }


def _tool_call_id(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        return str(tool_call.get("id") or "")
    return str(getattr(tool_call, "id", "") or "")


def _tool_call_function(tool_call: Any) -> tuple[str, Any]:
    if isinstance(tool_call, dict):
        function = tool_call.get("function") or {}
        return str(function.get("name") or ""), function.get("arguments") or "{}"
    function = getattr(tool_call, "function", None)
    return str(getattr(function, "name", "") or ""), (
        getattr(function, "arguments", "{}") or "{}"
    )


def _extract_dsml_text_tool_calls(content: str) -> tuple[str, list[dict]]:
    if "<｜｜DSML｜｜tool_calls>" not in content:
        return content, []

    tool_calls: list[dict] = []

    def collect_tool_calls(match: re.Match) -> str:
        block = match.group(1)
        for invoke_index, invoke_match in enumerate(
            re.finditer(
                r'<｜｜DSML｜｜invoke\s+name="([^"]+)">(.*?)</｜｜DSML｜｜invoke>',
                block,
                flags=re.DOTALL,
            ),
            start=len(tool_calls) + 1,
        ):
            arguments = {
                param_match.group(1): param_match.group(2).strip()
                for param_match in re.finditer(
                    r'<｜｜DSML｜｜parameter\s+name="([^"]+)"(?:\s+string="true")?>(.*?)</｜｜DSML｜｜parameter>',
                    invoke_match.group(2),
                    flags=re.DOTALL,
                )
            }
            tool_calls.append(
                {
                    "id": f"dsml_call_{invoke_index}",
                    "type": "function",
                    "function": {
                        "name": invoke_match.group(1).strip(),
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return ""

    visible_content = re.sub(
        r"<｜｜DSML｜｜tool_calls>(.*?)</｜｜DSML｜｜tool_calls>",
        collect_tool_calls,
        content,
        flags=re.DOTALL,
    ).strip()
    return visible_content, tool_calls


def _contains_dsml_tool_call_text(content: str) -> bool:
    return "<｜｜DSML｜｜tool_calls>" in (content or "")


def _append_no_more_tool_calls_instruction(messages: list[dict]) -> list[dict]:
    return [
        *messages,
        {
            "role": "system",
            "content": (
                "工具调用阶段已经结束。不要再输出工具调用、DSML、XML 或 JSON 工具请求；"
                "请直接基于已有知识库资料和工具返回结果，用 Markdown 回答用户问题。"
            ),
        },
    ]


def _normalize_tool_arguments(parsed: dict) -> dict:
    normalized = dict(parsed)
    if normalized.get("query"):
        return normalized

    for key in ("search_query", "keyword", "keywords", "q"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            normalized["query"] = value.strip()
            normalized.pop(key, None)
            return normalized

    queries = normalized.get("queries")
    if isinstance(queries, list):
        query = " ".join(str(item).strip() for item in queries if str(item).strip())
        if query:
            normalized["query"] = query
            normalized.pop("queries", None)
    elif isinstance(queries, str) and queries.strip():
        normalized["query"] = queries.strip()
        normalized.pop("queries", None)
    return normalized


def _parse_tool_arguments(raw_arguments: Any) -> dict:
    if isinstance(raw_arguments, dict):
        return _normalize_tool_arguments(raw_arguments)
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return _normalize_tool_arguments(parsed) if isinstance(parsed, dict) else {}


async def _complete_llm_answer_with_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    max_tool_calls: int = 2,
) -> tuple[str, str, list[dict]]:
    tool_run = await _prepare_llm_messages_with_tools(
        messages,
        tools=tools,
        tool_handlers=tool_handlers,
        max_tool_calls=max_tool_calls,
    )
    if tool_run.answer is not None:
        return tool_run.answer, tool_run.thinking, tool_run.messages

    llm_config = _resolve_llm_config()
    client = _get_llm_client(llm_config)
    response = client.chat.completions.create(
        model=llm_config["model"],
        messages=_append_no_more_tool_calls_instruction(tool_run.messages),
        temperature=0.5,
        **_build_thinking_completion_options(llm_config),
    )
    message = response.choices[0].message
    thinking, answer = _extract_thinking_and_answer(
        message.content or "",
        getattr(message, "reasoning_content", None),
    )
    if _contains_dsml_tool_call_text(answer):
        response = client.chat.completions.create(
            model=llm_config["model"],
            messages=_append_no_more_tool_calls_instruction(
                [
                    *tool_run.messages,
                    {
                        "role": "assistant",
                        "content": ("我刚刚仍输出了工具调用文本，这不是最终答案。"),
                    },
                ]
            ),
            temperature=0.5,
            **_build_thinking_completion_options(llm_config),
        )
        message = response.choices[0].message
        thinking, answer = _extract_thinking_and_answer(
            message.content or "",
            getattr(message, "reasoning_content", None),
        )
    return answer, thinking, tool_run.messages


async def _prepare_llm_messages_with_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    max_tool_calls: int = 2,
) -> LLMToolRunResult:
    llm_config = _resolve_llm_config()
    client = _get_llm_client(llm_config)
    working_messages = [*messages]
    executed_tool_calls = 0

    while executed_tool_calls < max_tool_calls:
        response = client.chat.completions.create(
            model=llm_config["model"],
            messages=working_messages,
            temperature=0.5,
            tools=tools,
            tool_choice="auto",
            **_build_thinking_completion_options(llm_config),
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            content, text_tool_calls = _extract_dsml_text_tool_calls(
                message.content or ""
            )
            if text_tool_calls:
                message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": text_tool_calls,
                }
                tool_calls = text_tool_calls
            else:
                thinking, answer = _extract_thinking_and_answer(
                    message.content or "",
                    getattr(message, "reasoning_content", None),
                )
                return LLMToolRunResult(
                    messages=working_messages,
                    answer=answer,
                    thinking=thinking,
                )

        if not tool_calls:
            thinking, answer = _extract_thinking_and_answer(
                message.content or "",
                getattr(message, "reasoning_content", None),
            )
            return LLMToolRunResult(
                messages=working_messages,
                answer=answer,
                thinking=thinking,
            )

        working_messages, executed_this_round = await _append_tool_call_results(
            working_messages,
            message,
            tool_calls,
            tool_handlers=tool_handlers,
            remaining_tool_calls=max_tool_calls - executed_tool_calls,
        )
        executed_tool_calls += executed_this_round

    return LLMToolRunResult(messages=working_messages)


async def _append_tool_call_results(
    working_messages: list[dict],
    message: Any,
    tool_calls: list[Any],
    *,
    tool_handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    remaining_tool_calls: int,
) -> tuple[list[dict], int]:
    executed_tool_calls = 0
    working_messages.append(_message_to_openai_dict(message))
    for tool_call in tool_calls:
        call_id = _tool_call_id(tool_call)
        name, raw_arguments = _tool_call_function(tool_call)
        handler = tool_handlers.get(name)
        if executed_tool_calls >= remaining_tool_calls:
            executed_tool_calls += 1
            content = {
                "error": "tool_call_limit_exceeded",
                "message": "联网搜索次数已达到上限",
            }
        elif handler is None:
            executed_tool_calls += 1
            content = {
                "error": "unknown_tool",
                "message": f"工具 {name or 'unknown'} 不可用",
            }
        else:
            executed_tool_calls += 1
            content = await handler(_parse_tool_arguments(raw_arguments))
        working_messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(content, ensure_ascii=False),
            }
        )
    return working_messages, executed_tool_calls


def _extract_thinking_and_answer(
    raw_answer: str, reasoning_content: Optional[str] = None
) -> tuple[str, str]:
    """提取思考内容与最终回答。优先使用原生 reasoning 字段。"""
    thinking = (reasoning_content or "").strip()
    answer = (raw_answer or "").strip()

    if thinking:
        return thinking, answer

    # 兼容提示词回退：<thinking>...</thinking> 或 <think>...</think>
    pattern = re.compile(
        r"<(?:thinking|think)>(.*?)</(?:thinking|think)>", re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(answer)
    if not match:
        return "", answer

    extracted = (match.group(1) or "").strip()
    cleaned = pattern.sub("", answer).strip()
    return extracted, cleaned


def _build_db_list_messages(context: str, question: str) -> list[dict]:
    """仅用标题/简介回答列表类问题"""
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户需要清单/列表类答案，请基于以下视频标题与简介回答。\n"
        "回答要：\n"
        "1. 按收藏夹或主题分组\n"
        "2. 只输出与问题相关的条目\n"
        "3. 简洁清晰\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _build_db_summary_messages(context: str, question: str) -> list[dict]:
    """仅用数据库内容回答总结类问题"""
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户需要总结/提炼，请基于以下视频内容回答。\n"
        "回答要：\n"
        "1. 提炼重点与要点\n"
        "2. 结构清晰、可快速理解\n"
        "3. 必要时引用视频标题作为来源\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def _is_list_question(question: str) -> bool:
    """列表/清单类问题"""
    list_terms = [
        "有哪些",
        "有什么",
        "列表",
        "清单",
        "目录",
        "都有哪些",
        "列出",
        "罗列",
        "多少个",
        "几个",
    ]
    return any(term in question for term in list_terms)


def _is_summary_question(question: str) -> bool:
    """总结/概括类问题"""
    summary_terms = [
        "总结",
        "概述",
        "概括",
        "分析",
        "梳理",
        "提炼",
        "回顾",
        "复盘",
        "要点",
        "重点",
        "关键点",
        "核心",
        "讲了什么",
        "讲些什么",
    ]
    return any(term in question for term in summary_terms)


def _is_general_question(question: str) -> bool:
    """通用闲聊/与收藏无关的问题"""
    general_terms = [
        "你好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "在吗",
        "你是谁",
        "你能做什么",
        "谢谢",
        "晚安",
        "早安",
        "早上好",
    ]
    cleaned = re.sub(r"[\\W_]+", "", question, flags=re.UNICODE)
    lowered = cleaned.lower()
    residual = lowered
    for term in general_terms:
        residual = residual.replace(term.lower(), "")
    return residual == ""


def _is_collection_intent(question: str) -> bool:
    """是否显式指向收藏/视频/知识库"""
    terms = [
        "收藏",
        "收藏夹",
        "视频",
        "合集",
        "up主",
        "BV",
        "bv",
        "分P",
        "字幕",
        "知识库",
        "入库",
        "同步",
        "向量",
        "检索",
    ]
    return any(term in question for term in terms)


def _is_overview_question(question: str) -> bool:
    """概览类问题（列表或总结）"""
    return _is_list_question(question) or _is_summary_question(question)


def _route_with_rules(question: str, is_collection_intent: bool, related: bool) -> str:
    """规则路由兜底"""
    if _is_general_question(question) and not is_collection_intent:
        return "direct"
    if _is_list_question(question):
        return "db_list"
    if _is_summary_question(question):
        return "db_content"
    if not related and not is_collection_intent:
        return "direct"
    return "vector"


def _route_with_llm(question: str) -> tuple[Optional[str], str]:
    """使用 LLM 进行路由判断"""
    try:
        llm_config = _resolve_llm_config()
        client = _get_llm_client(llm_config)
        system = (
            "你是一个路由器，只输出以下之一：direct, db_list, db_content, vector。\n"
            "规则：\n"
            "- direct：寒暄/闲聊/与收藏无关的问题\n"
            "- db_list：清单/列表/目录/有哪些\n"
            "- db_content：明确要求“全部/所有/整体/概览/全库”内容的总结\n"
            "- vector：具体主题问题或需要“先检索再总结”的问题\n"
            "示例：\n"
            "Q: 中西方文化的差异是什么，简单总结 -> vector\n"
            "Q: 概览我收藏夹里所有王德峰相关内容 -> db_content\n"
            "只输出一个词，不要解释。"
        )
        resp = client.chat.completions.create(
            model=llm_config["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        match = re.search(r"(direct|db_list|db_content|vector)", text)
        return (match.group(1) if match else None), text
    except Exception as e:
        logger.warning(f"LLM 路由失败: {e}")
        return None, ""


def _extract_keywords(question: str) -> List[str]:
    """提取用于过滤的关键词"""
    stopwords = {
        "什么",
        "怎么",
        "如何",
        "是否",
        "可以",
        "哪个",
        "哪些",
        "请问",
        "一下",
        "为什么",
        "有没有",
        "能不能",
        "能否",
        "是不是",
        "是什么",
        "多少",
        "哪里",
        "讲讲",
        "介绍",
        "总结",
        "概括",
        "分析",
        "解释",
        "说明",
        "评价",
        "区别",
        "内容",
        "视频",
    }
    keywords: List[str] = []
    for kw in re.findall(r"[\u4e00-\u9fff]{2,}", question):
        if kw not in stopwords and kw not in keywords:
            keywords.append(kw)
    for kw in re.findall(r"[A-Za-z0-9]{2,}", question):
        if kw not in keywords:
            keywords.append(kw)
    return keywords


def _filter_docs_by_keywords(docs: List[Document], question: str) -> List[Document]:
    """根据关键词过滤召回内容，减少噪声"""
    keywords = _extract_keywords(question)
    if not keywords:
        return []
    filtered: List[Document] = []
    for doc in docs:
        meta = doc.metadata or {}
        title = meta.get("title", "") or ""
        content = doc.page_content or ""
        if any(kw in title for kw in keywords) or any(kw in content for kw in keywords):
            filtered.append(doc)
    return filtered


async def _is_related_to_collection(
    db: AsyncSession, folder_ids: List[int], question: str
) -> bool:
    """判断问题是否与收藏夹内容有关"""
    if not folder_ids:
        return False
    keywords = _extract_keywords(question)
    if not keywords:
        return False
    like_conds = []
    for kw in keywords:
        pattern = f"%{kw}%"
        like_conds.append(VideoCache.title.ilike(pattern))
        like_conds.append(VideoCache.description.ilike(pattern))
        like_conds.append(VideoCache.content.ilike(pattern))
    stmt = (
        select(func.count())
        .select_from(VideoCache)
        .join(FavoriteVideo, FavoriteVideo.bvid == VideoCache.bvid)
        .where(FavoriteVideo.folder_id.in_(folder_ids))
        .where(or_(*like_conds))
    )
    count = await db.scalar(stmt)
    return (count or 0) > 0


async def _get_folder_ids_for_session(
    db: AsyncSession, session_id: str, media_ids: Optional[List[int]]
) -> List[int]:
    """根据 session 和 media_id 获取内部 folder_id（支持跨 session 查找同用户数据）"""
    from app.models import UserSession

    # 1. 尝试获取当前 session 的 mid
    mid_result = await db.execute(
        select(UserSession.bili_mid).where(UserSession.session_id == session_id)
    )
    mid = mid_result.scalar()
    target_session_ids = [session_id]
    if mid:
        # 查找该用户所有的 Session ID
        sessions_result = await db.execute(
            select(UserSession.session_id).where(UserSession.bili_mid == mid)
        )
        target_session_ids = [row[0] for row in sessions_result.fetchall()]
    # 构建查询：按 media_id 去重，只保留最新的一条
    stmt = (
        select(FavoriteFolder.id, FavoriteFolder.media_id, FavoriteFolder.updated_at)
        .where(FavoriteFolder.session_id.in_(target_session_ids))
        .order_by(FavoriteFolder.updated_at.desc())
    )
    if media_ids:
        stmt = stmt.where(FavoriteFolder.media_id.in_(media_ids))
    rows = await db.execute(stmt)
    dedup: dict[int, int] = {}
    for folder_id, media_id, _updated_at in rows.fetchall():
        if media_id not in dedup:
            dedup[media_id] = folder_id
    return list(dedup.values())


async def _get_bvids_by_folder_ids(
    db: AsyncSession, folder_ids: List[int]
) -> List[str]:
    """获取指定收藏夹的视频 BV 列表"""
    if not folder_ids:
        return []
    rows = await db.execute(
        select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id.in_(folder_ids))
    )
    bvids = []
    seen = set()
    for (bvid,) in rows.fetchall():
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        bvids.append(bvid)
    return bvids


async def _get_video_context(
    db: AsyncSession,
    folder_ids: List[int],
    include_content: bool = False,
    limit: Optional[int] = 50,
) -> tuple[str, List[dict]]:
    """获取视频上下文信息"""
    if not folder_ids:
        return "", []
    # 查询视频信息
    query = (
        select(
            FavoriteFolder.title.label("folder_title"),
            VideoCache.bvid,
            VideoCache.title,
            VideoCache.description,
            VideoCache.content if include_content else VideoCache.description,
        )
        .join(FavoriteVideo, FavoriteVideo.folder_id == FavoriteFolder.id)
        .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid, isouter=True)
        .where(FavoriteFolder.id.in_(folder_ids))
    )
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    records = result.fetchall()
    if not records:
        return "", []
    # 按收藏夹分组（对 bvid 去重，避免同一视频重复出现）
    grouped = {}
    sources = []
    seen_bvids = set()
    for folder_title, bvid, title, desc, content in records:
        if not bvid or not title:
            continue
        if bvid in seen_bvids:
            continue
        folder_name = folder_title or "默认收藏夹"
        if folder_name not in grouped:
            grouped[folder_name] = []
        video_info = f"- 《{title}》"
        if include_content and content:
            video_info += f"\n  摘要: {content}"
        elif desc:
            short_desc = desc[:100] + "..." if len(desc) > 100 else desc
            video_info += f" ({short_desc})"
        grouped[folder_name].append(video_info)
        seen_bvids.add(bvid)
        sources.append(
            {
                "bvid": bvid,
                "title": title,
                "url": f"https://www.bilibili.com/video/{bvid}",
            }
        )
    # 构建上下文文本
    context_parts = [
        f"【{folder_name}】\n" + "\n".join(videos)
        for folder_name, videos in grouped.items()
    ]
    context = "\n\n".join(context_parts)
    return context, sources


async def _get_video_titles_context(
    db: AsyncSession, folder_ids: List[int], limit: int = 50
) -> str:
    """获取收藏夹名称与视频标题（用于引导问题）"""
    if not folder_ids:
        return ""
    query = (
        select(
            FavoriteFolder.title.label("folder_title"),
            VideoCache.bvid,
            VideoCache.title,
        )
        .join(FavoriteVideo, FavoriteVideo.folder_id == FavoriteFolder.id)
        .join(VideoCache, VideoCache.bvid == FavoriteVideo.bvid, isouter=True)
        .where(FavoriteFolder.id.in_(folder_ids))
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.fetchall()
    if not records:
        return ""
    grouped = {}
    seen_bvids = set()
    for folder_title, bvid, title in records:
        if not title or not bvid:
            continue
        if bvid in seen_bvids:
            continue
        seen_bvids.add(bvid)
        folder_name = folder_title or "默认收藏夹"
        grouped.setdefault(folder_name, []).append(f"- 《{title}》")
    context_parts = [
        f"【{folder_name}】\n" + "\n".join(videos)
        for folder_name, videos in grouped.items()
    ]
    return "\n\n".join(context_parts)


async def _prepare_messages(
    request: ChatRequest, db: AsyncSession
) -> tuple[list[dict], List[dict], str]:
    """准备 LLM 消息与来源信息"""
    question = request.question.strip()
    rag = get_rag_service()
    folder_ids = []
    if request.session_id:
        folder_ids = await _get_folder_ids_for_session(
            db, request.session_id, request.folder_ids
        )
        logger.info(f"Session: {request.session_id}, 关联 FolderIDs: {folder_ids}")
    bvids = await _get_bvids_by_folder_ids(db, folder_ids) if folder_ids else []
    has_data = len(bvids) > 0
    is_collection_intent = _is_collection_intent(question)
    is_general = _is_general_question(question)
    if request.folder_ids:
        is_collection_intent = True
    # 1) LLM 路由优先，失败时降级规则路由
    logger.info(
        f"路由输入: question={question} folder_ids={folder_ids} has_data={has_data} is_collection_intent={is_collection_intent}"
    )
    route, route_raw = _route_with_llm(question)
    route_source = "LLM"
    related: Optional[bool] = None
    if not route:
        related = await _is_related_to_collection(db, folder_ids, question)
        route = _route_with_rules(question, is_collection_intent, related)
        route_source = "RULE"
    logger.info(f"路由策略: {route_source} => {route}")
    # 纠偏
    if is_general:
        route = "direct"
    # 2) 无数据时处理
    if not has_data:
        if is_collection_intent:
            context, sources = await _get_video_context(
                db, folder_ids, include_content=False, limit=50
            )
            if not context:
                context = "（暂无已入库的视频信息，请提醒用户可能需要先进行入库操作）"
            messages = _build_fallback_messages(context, question)
            return messages, sources, question
        messages = _build_direct_messages(question)
        return messages, [], question
    # 3) 直接回答
    if route == "direct":
        title_context = await _get_video_titles_context(db, folder_ids, limit=50)
        messages = (
            _build_direct_messages_with_context(title_context, question)
            if title_context
            else _build_direct_messages(question)
        )
        return messages, [], question
    # 4) 列表类问题
    if route == "db_list":
        if related is None:
            related = await _is_related_to_collection(db, folder_ids, question)
        if not related and not is_collection_intent:
            return _build_direct_messages(question), [], question
        context, sources = await _get_video_context(
            db, folder_ids, include_content=False, limit=50
        )
        if not context:
            return (
                _build_fallback_messages("（暂无信息，请入库）", question),
                sources,
                question,
            )
        return _build_db_list_messages(context, question), sources, question
    # 5) 总结类问题
    if route == "db_content":
        if related is None:
            related = await _is_related_to_collection(db, folder_ids, question)
        if not related and not is_collection_intent:
            return _build_direct_messages(question), [], question
        context, sources = await _get_video_context(
            db, folder_ids, include_content=True, limit=None
        )
        if not context:
            return (
                _build_fallback_messages("（暂无信息，请入库）", question),
                sources,
                question,
            )
        return _build_db_summary_messages(context, question), sources, question
    # 6) 检查相关性
    if related is None:
        related = await _is_related_to_collection(db, folder_ids, question)
    if not related and not is_collection_intent:
        return _build_direct_messages(question), [], question
    # 7) 向量检索
    docs = []
    try:
        docs = rag.search(question, k=5, bvids=bvids if bvids else None)
    except Exception as e:
        logger.warning(f"向量检索失败: {e}")
    if docs:
        filtered_docs = _filter_docs_by_keywords(docs, question)
        docs = filtered_docs if filtered_docs else docs
        context_parts, sources, seen_bvids = [], [], set()
        for doc in docs:
            bvid, title, content = (
                doc.metadata.get("bvid", ""),
                doc.metadata.get("title", ""),
                doc.page_content.strip(),
            )
            if content:
                context_parts.append(f"【{title}】\n{content}")
            if bvid and bvid not in seen_bvids:
                seen_bvids.add(bvid)
                sources.append(
                    {
                        "bvid": bvid,
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                    }
                )
        return (
            _build_rag_messages("\n\n---\n\n".join(context_parts), question),
            sources,
            question,
        )
    # 兜底
    context, sources = await _get_video_context(
        db, folder_ids, include_content=False, limit=50
    )
    return (
        _build_fallback_messages(context or "（暂无入库信息）", question),
        sources,
        question,
    )


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: Optional[ChatRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """智能问答"""
    _raise_legacy_scoped_api_required()
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        llm_config = _resolve_llm_config()
        messages, sources, _ = await _prepare_messages(request, db)
        messages = _enforce_markdown_output(messages)
        messages = _apply_mode_instructions(
            messages,
            bool(llm_config["thinking_config"]),
        )
        client = _get_llm_client(llm_config)
        try:
            response = client.chat.completions.create(
                model=llm_config["model"],
                messages=messages,
                temperature=0.5,
                **_build_thinking_completion_options(llm_config),
            )
            message = response.choices[0].message
            raw_answer = message.content or ""
            reasoning = getattr(message, "reasoning_content", None)
            thinking, answer = _extract_thinking_and_answer(raw_answer, reasoning)
            return ChatResponse(
                answer=answer, sources=sources[:5], thinking=thinking or None
            )
        except Exception as e:
            if _is_llm_connection_error(e):
                logger.warning(f"模型连接异常，使用降级回答: {e}")
                return ChatResponse(
                    answer=_build_llm_unavailable_answer(),
                    sources=sources[:5],
                    thinking=None,
                )
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")


@router.post("/ask/stream")
async def ask_question_stream(
    request: Optional[ChatRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """流式问答"""
    _raise_legacy_scoped_api_required()
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        llm_config = _resolve_llm_config()
        messages, sources, _ = await _prepare_messages(request, db)
        messages = _enforce_markdown_output(messages)
        messages = _apply_mode_instructions(
            messages,
            bool(llm_config["thinking_config"]),
        )

        def generate():
            thinking_parts: list[str] = []
            try:
                for event_type, content in _stream_llm_events(messages):
                    if event_type == "thinking":
                        thinking_parts.append(content)
                        yield _encode_thinking_delta(content)
                    else:
                        yield content
            except Exception as e:
                if _is_llm_connection_error(e):
                    logger.warning(f"流式模型连接异常，使用降级回答: {e}")
                    yield _build_llm_unavailable_answer()
                else:
                    raise
            if thinking_parts:
                yield f"\n[[THINKING_JSON]]{json.dumps(''.join(thinking_parts), ensure_ascii=False)}"
            yield f"\n[[SOURCES_JSON]]{json.dumps(sources, ensure_ascii=False)}"

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"流式问答失败: {str(e)}")


@router.post("/search")
async def search_videos(query: Optional[str] = None, k: int = 5):
    """搜索相关视频片段"""
    _raise_legacy_scoped_api_required()
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        rag = get_rag_service()
        docs = rag.search(query, k=k)
        results, seen_bvids = [], set()
        for doc in docs:
            bvid = doc.metadata.get("bvid", "")
            if bvid in seen_bvids:
                continue
            seen_bvids.add(bvid)
            results.append(
                {
                    "bvid": bvid,
                    "title": doc.metadata.get("title", ""),
                    "url": doc.metadata.get("url", ""),
                    "content_preview": (
                        doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content
                    ),
                }
            )
        return {"results": results}
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
