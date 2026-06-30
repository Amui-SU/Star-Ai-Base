import importlib.util
from types import SimpleNamespace


def test_write_env_values_to_path_updates_file_and_settings(tmp_path):
    assert importlib.util.find_spec("app.services.chat_config_env") is not None
    from app.services.chat_config_env import _read_env_values
    from app.services.chat_config_env import write_env_values_to_path

    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "# keep comments\nLLM_PROVIDER=dashscope\nKEEP=value\n",
        encoding="utf-8",
    )
    settings_obj = SimpleNamespace(
        llm_provider="dashscope",
        web_search_provider="auto",
    )

    write_env_values_to_path(
        env_path,
        {
            "LLM_PROVIDER": "deepseek",
            "WEB_SEARCH_PROVIDER": "tavily",
            "UNMAPPED_VALUE": "kept-on-disk",
        },
        settings_obj=settings_obj,
        settings_field_by_env={
            "LLM_PROVIDER": "llm_provider",
            "WEB_SEARCH_PROVIDER": "web_search_provider",
        },
    )

    assert env_path.read_text(encoding="utf-8") == (
        "# keep comments\n"
        "LLM_PROVIDER=deepseek\n"
        "KEEP=value\n"
        "\n"
        "WEB_SEARCH_PROVIDER=tavily\n"
        "UNMAPPED_VALUE=kept-on-disk\n"
    )
    assert settings_obj.llm_provider == "deepseek"
    assert settings_obj.web_search_provider == "tavily"
    assert not hasattr(settings_obj, "UNMAPPED_VALUE")
    assert _read_env_values(env_path) == (
        [
            "# keep comments",
            "LLM_PROVIDER=deepseek",
            "KEEP=value",
            "",
            "WEB_SEARCH_PROVIDER=tavily",
            "UNMAPPED_VALUE=kept-on-disk",
        ],
        {
            "LLM_PROVIDER": "deepseek",
            "KEEP": "value",
            "WEB_SEARCH_PROVIDER": "tavily",
            "UNMAPPED_VALUE": "kept-on-disk",
        },
    )
