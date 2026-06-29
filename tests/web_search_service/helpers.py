import pytest

from app.services import web_search


class FakeResolverResult:
    def __init__(self, host: str):
        self.host = host


@pytest.fixture(autouse=True)
def use_html_search_provider(monkeypatch):
    monkeypatch.setattr(web_search.settings, "web_search_provider", "html")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", True)
