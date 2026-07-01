import pytest

from app.services import web_search
from tests.web_search_tavily.helpers import FakeResolverResult


@pytest.mark.asyncio
async def test_search_web_uses_tavily_api_key_override(monkeypatch):
    captured = {"posts": []}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "User Tavily Result",
                        "url": "https://example.com/user-tavily",
                        "content": "User Tavily snippet",
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, json=None, headers=None):
            captured["posts"].append(
                {
                    "url": url,
                    "json": json,
                    "headers": headers,
                }
            )
            return FakeResponse()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.settings, "web_search_provider", "html")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", False)
    monkeypatch.setattr(web_search.settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web(
        "user tavily query",
        provider="tavily",
        tavily_api_key="user-tavily-key",
    )

    assert results == [
        {
            "title": "User Tavily Result",
            "url": "https://example.com/user-tavily",
            "snippet": "User Tavily snippet",
        }
    ]
    assert captured["posts"][0]["headers"] == {
        "Authorization": "Bearer user-tavily-key"
    }


@pytest.mark.asyncio
async def test_search_web_uses_request_provider_override(monkeypatch):
    captured = {"posts": []}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "Override Tavily Result",
                        "url": "https://example.com/override",
                        "content": "Override snippet",
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, json=None, headers=None):
            captured["posts"].append((url, data, json, headers))
            return FakeResponse()

        async def get(self, url, params):
            raise AssertionError("HTML provider should not run")

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.settings, "web_search_provider", "html")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    diagnostics = []
    results = await web_search.search_web(
        "override query",
        max_results=1,
        diagnostics=diagnostics,
        provider="tavily",
    )

    assert results == [
        {
            "title": "Override Tavily Result",
            "url": "https://example.com/override",
            "snippet": "Override snippet",
        }
    ]
    assert captured["posts"][0][0] == "https://api.tavily.com/search"
    assert diagnostics[0]["provider"] == "tavily"
