"""Environment-file persistence helpers for chat configuration."""

from pathlib import Path
from typing import Dict, Mapping

from app.config import settings

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
    "AGNES_API_KEY": "agnes_api_key",
    "AGNES_BASE_URL": "agnes_base_url",
    "AGNES_MODEL": "agnes_model",
    "AGNES_THINKING_CONFIG": "agnes_thinking_config",
    "CLAUDE_API_KEY": "claude_api_key",
    "CLAUDE_BASE_URL": "claude_base_url",
    "CLAUDE_MODEL": "claude_model",
    "CLAUDE_THINKING_CONFIG": "claude_thinking_config",
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
    "WEB_SEARCH_PROVIDER": "web_search_provider",
    "TAVILY_API_KEY": "tavily_api_key",
    "WEB_SEARCH_FALLBACK_HTML": "web_search_fallback_html",
    "TAVILY_SEARCH_DEPTH": "tavily_search_depth",
}


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


def write_env_values_to_path(
    path: Path,
    updates: Dict[str, str],
    *,
    settings_obj=settings,
    settings_field_by_env: Mapping[str, str] = SETTINGS_FIELD_BY_ENV,
) -> None:
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
        field = settings_field_by_env.get(key)
        if field:
            setattr(settings_obj, field, value)


def _write_env_values(updates: Dict[str, str]) -> None:
    write_env_values_to_path(_env_file_path(), updates)
