import pytest

from app.services import web_search


class FakeResolverResult:
    def __init__(self, host: str):
        self.host = host


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
async def test_search_web_falls_back_to_html_when_tavily_fails(monkeypatch):
    captured = {"requests": []}

    class FakeResponse:
        def __init__(self, text: str = ""):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, json=None, headers=None):
            captured["requests"].append(("POST", url, data, json))
            if url == "https://api.tavily.com/search":
                raise web_search.httpx.ConnectError("tavily unavailable")
            return FakeResponse("<html><body>no duckduckgo results</body></html>")

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params, None))
            if url == "https://search.yahoo.com/search":
                return FakeResponse(
                    """
                    <html><body>
                      <div class="dd algo algo-sr">
                        <div class="compTitle">
                          <a data-matarget="algo"
                             href="https://r.search.yahoo.com/_ylt=x/RV=2/RE=1/RO=10/RU=https%3a%2f%2fexample.com%2ffallback/RK=2/RS=x">
                            <h3 class="title"><span>Fallback Result</span></h3>
                          </a>
                        </div>
                        <div class="compText aAbs">
                          <p>Fallback snippet</p>
                        </div>
                      </div>
                    </body></html>
                    """
                )
            return FakeResponse("<html><body>no sogou results</body></html>")

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
        "fallback query",
        diagnostics=diagnostics,
    )

    assert results == [
        {
            "title": "Fallback Result",
            "url": "https://example.com/fallback",
            "snippet": "Fallback snippet",
        }
    ]
    assert [request[1] for request in captured["requests"]][:2] == [
        "https://api.tavily.com/search",
        "https://html.duckduckgo.com/html/",
    ]
    assert diagnostics[0]["provider"] == "tavily"
    assert diagnostics[0]["status"] == "failed"
    assert any(
        item["provider"] == "yahoo" and item["status"] == "success"
        for item in diagnostics
    )


@pytest.mark.asyncio
async def test_search_web_returns_empty_without_html_fallback_when_tavily_fails(
    monkeypatch,
):
    captured = {"posts": []}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, json=None, headers=None):
            captured["posts"].append(url)
            raise web_search.httpx.ConnectError("tavily unavailable")

        async def get(self, url, params):
            raise AssertionError("HTML fallback should not run")

    monkeypatch.setattr(web_search.settings, "web_search_provider", "tavily")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", False)
    monkeypatch.setattr(web_search.settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)

    diagnostics = []
    results = await web_search.search_web(
        "no fallback query",
        diagnostics=diagnostics,
    )

    assert results == []
    assert captured["posts"] == ["https://api.tavily.com/search"]
    assert [item["provider"] for item in diagnostics] == ["tavily"]
    assert diagnostics[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_search_web_reports_missing_tavily_key_without_html_fallback(
    monkeypatch,
):
    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, json=None, headers=None):
            raise AssertionError("Tavily should not run without an API key")

        async def get(self, url, params):
            raise AssertionError("HTML fallback should not run")

    monkeypatch.setattr(web_search.settings, "web_search_provider", "tavily")
    monkeypatch.setattr(web_search.settings, "tavily_api_key", "")
    monkeypatch.setattr(web_search.settings, "web_search_fallback_html", False)
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)

    diagnostics = []
    results = await web_search.search_web(
        "missing key query",
        diagnostics=diagnostics,
    )

    assert results == []
    assert diagnostics == [
        {
            "provider": "tavily",
            "status": "failed",
            "error": "missing_api_key",
            "message": "TAVILY_API_KEY is not configured",
            "proxy_configured": bool(web_search.settings.http_proxy.strip()),
        }
    ]


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
