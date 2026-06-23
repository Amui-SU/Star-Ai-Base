import asyncio

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


@pytest.mark.asyncio
async def test_fetch_web_page_rejects_private_network_urls():
    blocked_urls = [
        "http://127.0.0.1/admin",
        "http://localhost/admin",
        "http://10.0.0.1/admin",
        "http://172.16.0.1/admin",
        "http://192.168.1.10/admin",
        "file:///etc/passwd",
    ]

    for url in blocked_urls:
        result = await web_search.fetch_web_page(url)
        assert result["error"] == "blocked_url"
        assert result["content"] == ""


@pytest.mark.asyncio
async def test_fetch_web_page_rejects_hostnames_that_resolve_to_private_ips(
    monkeypatch,
):
    async def fake_getaddrinfo(hostname, port=80):
        assert hostname == "internal.example"
        return [FakeResolverResult("10.0.0.2")]

    monkeypatch.setattr(web_search, "_resolve_hostname", fake_getaddrinfo)

    result = await web_search.fetch_web_page("https://internal.example/admin")

    assert result["error"] == "blocked_url"
    assert result["content"] == ""


@pytest.mark.asyncio
async def test_fetch_web_page_extracts_clean_limited_text(monkeypatch):
    captured = {}

    class FakeResponse:
        text = """
        <html>
          <head>
            <title>示例页面</title>
            <style>.hidden { display: none; }</style>
            <script>alert("ignore")</script>
          </head>
          <body>
            <h1>标题</h1>
            <p>第一段内容。</p>
            <p>第二段内容。</p>
          </body>
        </html>
        """
        headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield self.text.encode("utf-8")

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url):
            assert method == "GET"
            captured["url"] = url
            return FakeStream()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    result = await web_search.fetch_web_page(
        "https://example.com/article",
        max_chars=12,
    )

    assert captured["url"] == "https://example.com/article"
    assert captured["client_kwargs"]["follow_redirects"] is False
    assert result["url"] == "https://example.com/article"
    assert result["title"] == "示例页面"
    assert result["content"] == "标题 第一段内容。"
    assert "alert" not in result["content"]
    assert "hidden" not in result["content"]


@pytest.mark.asyncio
async def test_fetch_web_page_decodes_charset_from_content_type(monkeypatch):
    html = """
    <html>
      <head><title>编码页面</title></head>
      <body><p>中文正文。</p></body>
    </html>
    """.encode(
        "gbk"
    )

    class FakeResponse:
        headers = {"content-type": "text/html; charset=gbk"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield html

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url):
            return FakeStream()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    result = await web_search.fetch_web_page("https://example.com/gbk")

    assert result["title"] == "编码页面"
    assert result["content"] == "中文正文。"


@pytest.mark.asyncio
async def test_fetch_web_page_falls_back_when_charset_is_unknown(monkeypatch):
    class FakeResponse:
        headers = {"content-type": "text/html; charset=made-up-charset"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield "<html><title>Fallback</title><body>正文</body></html>".encode()

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url):
            return FakeStream()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    result = await web_search.fetch_web_page("https://example.com/unknown-charset")

    assert "error" not in result
    assert result["title"] == "Fallback"
    assert result["content"] == "正文"


@pytest.mark.asyncio
async def test_fetch_web_page_reads_at_most_limited_bytes(monkeypatch):
    captured = {"chunks_read": 0}

    class FakeResponse:
        headers = {"content-type": "text/html; charset=utf-8"}
        status_code = 200

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            captured["chunks_read"] += 1
            yield b"<html><title>Limited</title><body>abcdefghij"
            captured["chunks_read"] += 1
            yield b"this chunk should not be read</body></html>"

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url):
            assert method == "GET"
            assert url == "https://example.com/large"
            return FakeStream()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    result = await web_search.fetch_web_page(
        "https://example.com/large",
        max_bytes=40,
    )

    assert captured["chunks_read"] == 1
    assert result["title"] == "Limited"
    assert "this chunk should not be read" not in result["content"]


@pytest.mark.asyncio
async def test_fetch_web_page_rejects_non_text_content_type(monkeypatch):
    class FakeResponse:
        headers = {"content-type": "application/pdf"}
        status_code = 200

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            raise AssertionError("unsupported content should not be read")

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url):
            return FakeStream()

    async def fake_resolve_hostname(hostname, port=80):
        return [FakeResolverResult("93.184.216.34")]

    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(web_search, "_resolve_hostname", fake_resolve_hostname)

    result = await web_search.fetch_web_page("https://example.com/file.pdf")

    assert result["error"] == "unsupported_content_type"
    assert result["content"] == ""


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
