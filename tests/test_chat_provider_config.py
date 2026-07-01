import importlib.util
import json


def test_save_global_llm_provider_config_verifies_and_writes():
    assert importlib.util.find_spec("app.services.chat_provider_config") is not None
    from app.services.chat_provider_config import save_global_llm_provider_config

    writes: list[dict[str, str]] = []
    verified: list[dict] = []
    reset_calls: list[bool] = []

    def resolve_llm_config(provider=None):
        return {
            "provider": provider or "deepseek",
            "provider_label": "DeepSeek",
            "api_key": "saved-key",
            "base_url": "https://api.deepseek.test",
            "model": "deepseek-chat",
            "thinking_config": {"thinking": {"type": "enabled"}},
        }

    response = save_global_llm_provider_config(
        provider="deepseek",
        thinking_mode="standard",
        verifier=lambda config: verified.append(config) or 123,
        resolve_llm_config=resolve_llm_config,
        get_provider_thinking_template=lambda _provider: {
            "thinking": {"type": "enabled"}
        },
        env_writer=lambda updates: writes.append(updates),
        reset_rag=lambda: reset_calls.append(True),
        warning_logger=lambda _message: None,
        info_logger=lambda _message: None,
    )

    assert verified[0]["thinking_config"] == {"thinking": {"type": "enabled"}}
    assert writes == [
        {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "saved-key",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.test",
            "DEEPSEEK_MODEL": "deepseek-chat",
            "DEEPSEEK_THINKING_CONFIG": json.dumps(
                {"thinking": {"type": "enabled"}},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    ]
    assert reset_calls == [True]
    assert response["ok"] is True
    assert response["current_provider"] == "deepseek"
    assert response["latency_ms"] == 123


def test_set_global_llm_provider_writes_selected_provider():
    assert importlib.util.find_spec("app.services.chat_provider_config") is not None
    from app.services.chat_provider_config import set_global_llm_provider

    writes: list[dict[str, str]] = []

    response = set_global_llm_provider(
        "deepseek",
        resolve_llm_config=lambda _provider: {
            "provider": "deepseek",
            "provider_label": "DeepSeek",
            "api_key": "configured-key",
            "model": "deepseek-chat",
        },
        env_writer=lambda updates: writes.append(updates),
        info_logger=lambda _message: None,
    )

    assert writes == [{"LLM_PROVIDER": "deepseek"}]
    assert response == {
        "ok": True,
        "current_provider": "deepseek",
        "model": "deepseek-chat",
        "provider_label": "DeepSeek",
    }
