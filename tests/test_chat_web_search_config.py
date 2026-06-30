import importlib.util

import pytest
from fastapi import HTTPException


def test_web_search_config_helper_normalizes_and_writes(monkeypatch):
    assert importlib.util.find_spec("app.services.chat_web_search_config") is not None
    from app.config import settings
    from app.services.chat_web_search_config import _normalize_tavily_search_depth
    from app.services.chat_web_search_config import _normalize_web_search_provider
    from app.services.chat_web_search_config import save_global_web_search_config

    writes: list[dict[str, str]] = []
    monkeypatch.setattr(settings, "web_search_provider", "auto")
    monkeypatch.setattr(settings, "web_search_fallback_html", True)
    monkeypatch.setattr(settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(settings, "tavily_api_key", "")

    assert _normalize_web_search_provider(" HTML ") == "html"
    assert _normalize_tavily_search_depth(" ADVANCED ") == "advanced"

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


def test_web_search_config_helper_rejects_missing_tavily_key(monkeypatch):
    assert importlib.util.find_spec("app.services.chat_web_search_config") is not None
    from app.config import settings
    from app.services.chat_web_search_config import save_global_web_search_config

    monkeypatch.setattr(settings, "tavily_api_key", "")

    with pytest.raises(HTTPException) as exc:
        save_global_web_search_config(provider="tavily")

    assert exc.value.status_code == 400
