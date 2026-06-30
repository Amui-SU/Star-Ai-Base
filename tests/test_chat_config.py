from types import SimpleNamespace

from app.services.api_credentials import (
    LLM_API_SOURCE_OFFICIAL,
    LLM_API_SOURCE_PERSONAL,
)
from app.services.chat_config import current_user_llm_source
from app.services.chat_config import save_global_web_search_config
from app.services.chat_config import set_global_llm_provider


def test_current_user_llm_source_prefers_saved_source():
    user = SimpleNamespace(llm_api_source=LLM_API_SOURCE_OFFICIAL)

    assert (
        current_user_llm_source(user, has_personal=True, has_official=True)
        == LLM_API_SOURCE_OFFICIAL
    )


def test_current_user_llm_source_falls_back_to_available_credentials():
    user = SimpleNamespace(llm_api_source=None)

    assert (
        current_user_llm_source(user, has_personal=True, has_official=True)
        == LLM_API_SOURCE_PERSONAL
    )
    assert (
        current_user_llm_source(user, has_personal=False, has_official=True)
        == LLM_API_SOURCE_OFFICIAL
    )
    assert (
        current_user_llm_source(user, has_personal=False, has_official=False)
        == LLM_API_SOURCE_PERSONAL
    )


def test_save_global_web_search_config_writes_normalized_values(monkeypatch):
    from app.config import settings

    writes: list[dict[str, str]] = []
    monkeypatch.setattr(settings, "web_search_provider", "auto")
    monkeypatch.setattr(settings, "web_search_fallback_html", True)
    monkeypatch.setattr(settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(settings, "tavily_api_key", "")

    response = save_global_web_search_config(
        provider="TAVILY",
        tavily_api_key=" tvly-test ",
        fallback_html=False,
        tavily_search_depth="ADVANCED",
        env_writer=lambda updates: writes.append(updates),
    )

    assert writes == [
        {
            "WEB_SEARCH_PROVIDER": "tavily",
            "WEB_SEARCH_FALLBACK_HTML": "false",
            "TAVILY_SEARCH_DEPTH": "advanced",
            "TAVILY_API_KEY": "tvly-test",
        }
    ]
    assert response["provider"] == "tavily"
    assert response["fallback_html"] is False
    assert response["tavily_search_depth"] == "advanced"


def test_set_global_llm_provider_writes_selected_provider(monkeypatch):
    from app.config import settings

    writes: list[dict[str, str]] = []
    monkeypatch.setattr(settings, "deepseek_api_key", "configured-key")

    response = set_global_llm_provider(
        "deepseek",
        env_writer=lambda updates: writes.append(updates),
        info_logger=lambda _message: None,
    )

    assert writes == [{"LLM_PROVIDER": "deepseek"}]
    assert response == {
        "ok": True,
        "current_provider": "deepseek",
        "model": settings.deepseek_model,
        "provider_label": "DeepSeek",
    }
