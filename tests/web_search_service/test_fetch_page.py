import pytest

from app.services import web_search

from .helpers import FakeResolverResult, use_html_search_provider


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
