import pytest

from app.services import web_search

from .helpers import FakeResolverResult, use_html_search_provider


@pytest.mark.asyncio
async def test_search_web_allows_proxy_fake_ip_dns_results(monkeypatch):
    class FakeResponse:
        text = """
        <a class="result__a" href="https://safe.example/page">Safe Result</a>
        """

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

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("198.18.0.80")]

    async def fake_resolve_public_hostname(hostname):
        return ["93.184.216.34"]

    monkeypatch.setattr(web_search.settings, "http_proxy", "http://127.0.0.1:7890")
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)
    monkeypatch.setattr(
        web_search,
        "_resolve_public_hostname",
        fake_resolve_public_hostname,
        raising=False,
    )

    results = await web_search.search_web("proxied query")

    assert results == [
        {
            "title": "Safe Result",
            "url": "https://safe.example/page",
            "snippet": "",
        }
    ]


@pytest.mark.asyncio
async def test_proxy_fake_ip_dns_result_is_blocked_without_public_dns(monkeypatch):
    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("198.18.0.80")]

    async def fake_resolve_public_hostname(hostname):
        return []

    monkeypatch.setattr(web_search.settings, "http_proxy", "http://127.0.0.1:7890")
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)
    monkeypatch.setattr(
        web_search,
        "_resolve_public_hostname",
        fake_resolve_public_hostname,
        raising=False,
    )

    assert await web_search._is_blocked_url("https://internal.example/admin") is True


@pytest.mark.asyncio
async def test_proxy_fake_ip_dns_result_is_blocked_when_public_dns_is_private(
    monkeypatch,
):
    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("198.18.0.80")]

    async def fake_resolve_public_hostname(hostname):
        return ["10.0.0.2"]

    monkeypatch.setattr(web_search.settings, "http_proxy", "http://127.0.0.1:7890")
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)
    monkeypatch.setattr(
        web_search,
        "_resolve_public_hostname",
        fake_resolve_public_hostname,
        raising=False,
    )

    assert await web_search._is_blocked_url("https://private.example/admin") is True
