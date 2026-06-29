import asyncio

import pytest

from app.services import web_search

from .helpers import FakeResolverResult, use_html_search_provider


@pytest.mark.asyncio
async def test_search_web_filters_unsafe_result_urls(monkeypatch):
    class FakeResponse:
        text = """
        <a class="result__a" href="https://safe.example/page">安全结果</a>
        <a class="result__a" href="http://127.0.0.1/admin">内网结果</a>
        <a class="result__a" href="file:///etc/passwd">文件结果</a>
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
        if hostname == "safe.example":
            return [FakeResolverResult("93.184.216.34")]
        return []

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web("测试")

    assert results == [
        {
            "title": "安全结果",
            "url": "https://safe.example/page",
            "snippet": "",
        }
    ]


@pytest.mark.asyncio
async def test_search_web_falls_back_to_yahoo_results(monkeypatch):
    captured = {"requests": []}

    class FakeResponse:
        def __init__(self, text: str):
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

        async def post(self, url, data):
            captured["requests"].append(("POST", url, data))
            return FakeResponse("<html><body>no duckduckgo results</body></html>")

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params))
            if url == "https://www.sogou.com/web":
                return FakeResponse("<html><body>no sogou results</body></html>")
            return FakeResponse(
                """
                <html><body>
                  <div class="dd algo algo-sr">
                    <div class="compTitle">
                      <a data-matarget="algo"
                         href="https://r.search.yahoo.com/_ylt=x/RV=2/RE=1/RO=10/RU=https%3a%2f%2fexample.com%2farticle/RK=2/RS=x">
                        <h3 class="title"><span>Yahoo Result Title</span></h3>
                      </a>
                    </div>
                    <div class="compText aAbs">
                      <p>Yahoo result snippet</p>
                    </div>
                  </div>
                </body></html>
                """
            )

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web("fallback query")

    assert captured["requests"][1][1] == "https://search.yahoo.com/search"
    assert results == [
        {
            "title": "Yahoo Result Title",
            "url": "https://example.com/article",
            "snippet": "Yahoo result snippet",
        }
    ]


@pytest.mark.asyncio
async def test_search_web_returns_fast_provider_without_waiting_for_slow_provider(
    monkeypatch,
):
    captured = {"requests": [], "cancelled": []}

    class FakeResponse:
        def __init__(self, text: str):
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

        async def post(self, url, data):
            captured["requests"].append(("POST", url, data))
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                captured["cancelled"].append("duckduckgo")
                raise
            return FakeResponse("<html><body>slow duckduckgo</body></html>")

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params))
            if url == "https://search.yahoo.com/search":
                return FakeResponse(
                    """
                    <html><body>
                      <div class="dd algo algo-sr">
                        <div class="compTitle">
                          <a data-matarget="algo"
                             href="https://r.search.yahoo.com/_ylt=x/RV=2/RE=1/RO=10/RU=https%3a%2f%2ffast.example%2farticle/RK=2/RS=x">
                            <h3 class="title"><span>Fast Yahoo Result</span></h3>
                          </a>
                        </div>
                        <div class="compText aAbs">
                          <p>Fast Yahoo snippet</p>
                        </div>
                      </div>
                    </body></html>
                    """
                )
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                captured["cancelled"].append("sogou")
                raise
            return FakeResponse("<html><body>slow sogou</body></html>")

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await asyncio.wait_for(
        web_search.search_web("fast provider query", max_results=1),
        timeout=0.5,
    )

    assert results == [
        {
            "title": "Fast Yahoo Result",
            "url": "https://fast.example/article",
            "snippet": "Fast Yahoo snippet",
        }
    ]
    assert set(captured["cancelled"]) == {"duckduckgo", "sogou"}


@pytest.mark.asyncio
async def test_search_web_continues_to_fallback_when_provider_raises(monkeypatch):
    captured = {"requests": []}

    class FakeResponse:
        text = """
        <html><body>
          <div class="dd algo algo-sr">
            <div class="compTitle">
              <a data-matarget="algo"
                 href="https://r.search.yahoo.com/_ylt=x/RV=2/RE=1/RO=10/RU=https%3a%2f%2fexample.com%2fbackup/RK=2/RS=x">
                <h3 class="title"><span>Backup Result</span></h3>
              </a>
            </div>
            <div class="compText aAbs">
              <p>Backup snippet</p>
            </div>
          </div>
        </body></html>
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
            captured["requests"].append(("POST", url, data))
            raise RuntimeError("duckduckgo unavailable")

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params))
            return FakeResponse()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web("fallback query")

    assert captured["requests"][1][1] == "https://search.yahoo.com/search"
    assert results == [
        {
            "title": "Backup Result",
            "url": "https://example.com/backup",
            "snippet": "Backup snippet",
        }
    ]


@pytest.mark.asyncio
async def test_search_web_aggregates_results_from_multiple_providers(monkeypatch):
    captured = {"requests": []}

    class FakeResponse:
        def __init__(self, text: str):
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

        async def post(self, url, data):
            captured["requests"].append(("POST", url, data))
            return FakeResponse(
                """
                <a class="result__a" href="https://example.com/duck">Duck Result</a>
                """
            )

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params))
            if url == "https://search.yahoo.com/search":
                return FakeResponse(
                    """
                    <html><body>
                      <div class="dd algo algo-sr">
                        <div class="compTitle">
                          <a data-matarget="algo"
                             href="https://r.search.yahoo.com/_ylt=x/RV=2/RE=1/RO=10/RU=https%3a%2f%2fexample.com%2fyahoo/RK=2/RS=x">
                            <h3 class="title"><span>Yahoo Result</span></h3>
                          </a>
                        </div>
                      </div>
                    </body></html>
                    """
                )
            return FakeResponse(
                """
                <html><body>
                  <div class="vrwrap">
                    <h3 class="vr-title">
                      <a href="/link?url=sogou-token">Sogou Result</a>
                    </h3>
                    <cite>https://example.com/sogou</cite>
                  </div>
                </body></html>
                """
            )

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web("aggregate query", max_results=3)

    assert [request[1] for request in captured["requests"]] == [
        "https://html.duckduckgo.com/html/",
        "https://search.yahoo.com/search",
        "https://www.sogou.com/web",
    ]
    assert [result["url"] for result in results] == [
        "https://example.com/duck",
        "https://example.com/yahoo",
        "https://example.com/sogou",
    ]


@pytest.mark.asyncio
async def test_search_web_falls_back_when_duckduckgo_is_challenged(monkeypatch):
    captured = {"requests": []}

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            captured["requests"].append(("POST", url, data))
            return FakeResponse("<html><body>anomaly-modal challenge</body></html>")

        async def get(self, url, params):
            captured["requests"].append(("GET", url, params))
            return FakeResponse(
                """
                <html><body>
                  <div class="vrwrap">
                    <h3 class="vr-title">
                      <a href="/link?url=fallback-token">备用结果标题</a>
                    </h3>
                    <p class="str_info">备用结果摘要</p>
                    <cite>https://example.com/fallback</cite>
                  </div>
                </body></html>
                """
            )

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    results = await web_search.search_web("被拦截查询")

    assert captured["client_kwargs"]["trust_env"] is False
    assert captured["requests"][0][0] == "POST"
    assert captured["requests"][1][0] == "GET"
    assert results == [
        {
            "title": "备用结果标题",
            "url": "https://example.com/fallback",
            "snippet": "备用结果摘要",
        }
    ]
