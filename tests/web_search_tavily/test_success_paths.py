import pytest

from app.services import web_search
from tests.web_search_tavily.helpers import FakeResolverResult


@pytest.mark.asyncio
async def test_search_web_uses_tavily_provider_when_configured(monkeypatch):
    captured = {"posts": []}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "Tavily Result",
                        "url": "https://example.com/tavily",
                        "content": "Tavily snippet",
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
                    "data": data,
                    "json": json,
                    "headers": headers,
                }
            )
            return FakeResponse()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.settings, "web_search_provider", "tavily")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", True)
    monkeypatch.setattr(web_search.settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    diagnostics = []
    results = await web_search.search_web(
        "tavily query",
        max_results=2,
        diagnostics=diagnostics,
    )

    assert results == [
        {
            "title": "Tavily Result",
            "url": "https://example.com/tavily",
            "snippet": "Tavily snippet",
        }
    ]
    assert captured["posts"] == [
        {
            "url": "https://api.tavily.com/search",
            "data": None,
            "json": {
                "query": "tavily query",
                "search_depth": "basic",
                "max_results": 2,
                "include_answer": False,
            },
            "headers": {"Authorization": "Bearer test-key"},
        }
    ]
    assert diagnostics[0]["provider"] == "tavily"
    assert diagnostics[0]["status"] == "success"
    assert diagnostics[0]["result_count"] == 1


@pytest.mark.asyncio
async def test_search_web_keeps_tavily_snippets_when_dns_lookup_fails(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "Tavily DNS Result",
                        "url": "https://example.com/tavily-dns",
                        "content": "Tavily snippet should still ground the model",
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
            return FakeResponse()

    async def unresolved_hostname(hostname, port=80):
        return []

    monkeypatch.setattr(web_search.settings, "web_search_provider", "tavily")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", False)
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", unresolved_hostname)

    results = await web_search.search_web("tavily dns query")

    assert results == [
        {
            "title": "Tavily DNS Result",
            "url": "https://example.com/tavily-dns",
            "snippet": "Tavily snippet should still ground the model",
        }
    ]


@pytest.mark.asyncio
async def test_search_web_auto_uses_tavily_when_key_is_configured(monkeypatch):
    captured = {"posts": []}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "Auto Tavily Result",
                        "url": "https://example.com/auto",
                        "content": "Auto snippet",
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
            captured["posts"].append(url)
            return FakeResponse()

        async def get(self, url, params):
            raise AssertionError("HTML provider should not run when Tavily succeeds")

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.settings, "web_search_provider", "html")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    diagnostics = []
    results = await web_search.search_web(
        "auto query",
        diagnostics=diagnostics,
        provider="auto",
    )

    assert results[0]["url"] == "https://example.com/auto"
    assert captured["posts"] == ["https://api.tavily.com/search"]
    assert diagnostics[0]["provider"] == "tavily"
