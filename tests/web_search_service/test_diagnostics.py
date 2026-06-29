import asyncio

import pytest

from app.services import web_search

from .helpers import FakeResolverResult, use_html_search_provider


@pytest.mark.asyncio
async def test_search_web_records_provider_diagnostics_when_all_sources_fail(
    monkeypatch,
):
    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            raise web_search.httpx.ConnectError("proxy connection refused")

        async def get(self, url, params):
            raise web_search.httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(web_search.settings, "http_proxy", "")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)

    diagnostics = []
    results = await web_search.search_web(
        "diagnostic query",
        diagnostics=diagnostics,
    )

    assert results == []
    assert [item["provider"] for item in diagnostics] == [
        "duckduckgo",
        "yahoo",
        "sogou",
    ]
    assert all(item["status"] == "failed" for item in diagnostics)
    assert diagnostics[0]["error"] == "ConnectError"
    assert diagnostics[0]["message"] == "proxy connection refused"
    assert diagnostics[0]["proxy_configured"] is False


@pytest.mark.asyncio
async def test_search_web_reports_provider_diagnostics_in_stable_order(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            await asyncio.sleep(0.03)
            raise web_search.httpx.ConnectError("duckduckgo failed last")

        async def get(self, url, params):
            if url == "https://search.yahoo.com/search":
                await asyncio.sleep(0.02)
                raise web_search.httpx.ConnectTimeout("yahoo failed second")
            raise web_search.httpx.ReadTimeout("sogou failed first")

    monkeypatch.setattr(web_search.settings, "http_proxy", "")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)

    diagnostics = []
    results = await web_search.search_web(
        "stable diagnostic query",
        diagnostics=diagnostics,
    )

    assert results == []
    assert [item["provider"] for item in diagnostics] == [
        "duckduckgo",
        "yahoo",
        "sogou",
    ]
    assert [item["message"] for item in diagnostics] == [
        "duckduckgo failed last",
        "yahoo failed second",
        "sogou failed first",
    ]


@pytest.mark.asyncio
async def test_search_web_records_empty_provider_diagnostics(monkeypatch):
    class FakeResponse:
        text = "<html><body>no parsable results</body></html>"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            return FakeResponse()

        async def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)

    diagnostics = []
    results = await web_search.search_web(
        "empty diagnostic query",
        diagnostics=diagnostics,
    )

    assert results == []
    assert [item["status"] for item in diagnostics] == ["empty", "empty", "empty"]
    assert diagnostics[0]["message"] == "搜索源返回空结果"
