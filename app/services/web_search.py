from html.parser import HTMLParser
import asyncio
import ipaddress
import re
import socket
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from loguru import logger

from app.config import settings

MAX_SEARCH_QUERY_CHARS = 240
MAX_SEARCH_TITLE_CHARS = 180
MAX_SEARCH_SNIPPET_CHARS = 600
SEARCH_PROVIDERS = ("tavily", "duckduckgo", "yahoo", "sogou")


async def _cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    pending_tasks = [task for task in tasks if not task.done()]
    if not pending_tasks:
        return
    for task in pending_tasks:
        task.cancel()
    await asyncio.gather(*pending_tasks, return_exceptions=True)


def _sort_provider_diagnostics(diagnostics: list[dict] | None) -> None:
    if diagnostics is None:
        return
    provider_order = {
        provider: index for index, provider in enumerate(SEARCH_PROVIDERS)
    }
    diagnostics.sort(
        key=lambda item: provider_order.get(
            str(item.get("provider") or ""),
            len(provider_order),
        )
    )


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        class_name = attr.get("class") or ""
        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": self._normalize_url(attr.get("href"))}
            self._capture = "title"
            self._text_parts = []
        elif (
            self._current is not None
            and tag in {"a", "div"}
            and ("result__snippet" in class_name or "result__body" in class_name)
        ):
            self._capture = "snippet"
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None or self._capture is None:
            return
        if self._capture == "title" and tag == "a":
            self._current["title"] = " ".join(self._text_parts).strip()
            self._capture = None
            self._text_parts = []
            if self._current["title"] and self._current["url"]:
                self.results.append(self._current)
        elif self._capture == "snippet" and tag in {"a", "div"}:
            snippet = " ".join(self._text_parts).strip()
            if snippet:
                self._current["snippet"] = snippet
            self._capture = None
            self._text_parts = []

    @staticmethod
    def _normalize_url(raw_url: str | None) -> str:
        if not raw_url:
            return ""
        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        parsed = urlparse(raw_url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(uddg)
        return raw_url


class _SogouResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._text_parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        class_name = attr.get("class") or ""
        if tag == "div" and "vrwrap" in class_name:
            self._current = {"title": "", "url": "", "snippet": ""}
            self._depth = 1
            return
        if self._current is None:
            return
        self._depth += 1
        if tag == "a" and not self._current["url"]:
            self._current["url"] = self._normalize_url(attr.get("href"))
            self._capture = "title"
            self._text_parts = []
        elif tag in {"p", "div"} and (
            "str_info" in class_name or "fz-mid" in class_name
        ):
            self._capture = "snippet"
            self._text_parts = []
        elif tag == "cite":
            self._capture = "cite"
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._capture:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        if self._capture == "title" and tag == "a":
            self._current["title"] = _compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "snippet" and tag in {"p", "div"}:
            self._current["snippet"] = _compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "cite" and tag == "cite":
            cite = self._normalize_url(_compact_text(" ".join(self._text_parts)))
            if cite.startswith(("http://", "https://")) and (
                not self._current["url"]
                or self._is_sogou_redirect_url(self._current["url"])
            ):
                self._current["url"] = cite
            self._capture = None
            self._text_parts = []

        self._depth -= 1
        if self._depth <= 0:
            title = self._current.get("title", "")
            url = self._current.get("url", "")
            if title and url:
                self.results.append(self._current)
            self._current = None
            self._capture = None
            self._text_parts = []

    @staticmethod
    def _normalize_url(raw_url: str | None) -> str:
        if not raw_url:
            return ""
        if raw_url.startswith("//"):
            return f"https:{raw_url}"
        if raw_url.startswith("/"):
            return urljoin("https://www.sogou.com", raw_url)
        return raw_url

    @staticmethod
    def _is_sogou_redirect_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.endswith("sogou.com") and parsed.path.startswith("/link")


class _YahooResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._text_parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        class_name = attr.get("class") or ""
        if tag == "div" and "algo-sr" in class_name:
            self._current = {"title": "", "url": "", "snippet": ""}
            self._depth = 1
            return
        if self._current is None:
            return

        self._depth += 1
        if (
            tag == "a"
            and attr.get("data-matarget") == "algo"
            and not self._current["url"]
        ):
            self._current["url"] = self._normalize_url(attr.get("href"))
        elif tag == "h3" and self._current["url"] and not self._current["title"]:
            self._capture = "title"
            self._text_parts = []
        elif tag == "p" and self._current["title"] and not self._current["snippet"]:
            self._capture = "snippet"
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._capture:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return

        if self._capture == "title" and tag == "h3":
            self._current["title"] = _compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "snippet" and tag == "p":
            self._current["snippet"] = _compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []

        self._depth -= 1
        if self._depth <= 0:
            title = self._current.get("title", "")
            url = self._current.get("url", "")
            if title and url:
                self.results.append(self._current)
            self._current = None
            self._capture = None
            self._text_parts = []

    @staticmethod
    def _normalize_url(raw_url: str | None) -> str:
        if not raw_url:
            return ""
        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        parsed = urlparse(raw_url)
        if parsed.netloc.endswith("search.yahoo.com"):
            for segment in parsed.path.split("/"):
                if segment.startswith("RU="):
                    return unquote(segment.removeprefix("RU="))
        return raw_url


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._capture_title = False
        self._skip_depth = 0
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._skip_depth > 0:
            return
        if self._capture_title:
            self.title = _compact_text(f"{self.title} {text}")
            return
        self._text_parts.append(text)

    @property
    def content(self) -> str:
        return _compact_text(" ".join(self._text_parts))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate_text(text: str, max_chars: int) -> str:
    limit = max(0, max_chars)
    if len(text) <= limit:
        return text
    truncated = text[:limit].strip()
    boundary = max(truncated.rfind(mark) for mark in "。！？.!?")
    if boundary > 0:
        return truncated[: boundary + 1].strip()
    return truncated


def _is_supported_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return (
        not normalized
        or normalized == "text/html"
        or normalized == "text/plain"
        or normalized.endswith("+html")
    )


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([^\s;]+)", content_type, re.IGNORECASE)
    if not match:
        return "utf-8"
    return match.group(1).strip("\"'") or "utf-8"


def _decode_body(body: bytes, charset: str) -> str:
    try:
        return body.decode(charset, errors="ignore")
    except LookupError:
        return body.decode("utf-8", errors="ignore")


def _is_blocked_address(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _is_proxy_fake_ip_address(host: str) -> bool:
    if not settings.http_proxy.strip():
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address in ipaddress.ip_network("198.18.0.0/15")


async def _resolve_hostname(hostname: str, port: int = 80) -> list:
    loop = asyncio.get_running_loop()
    try:
        return await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []


async def _resolve_public_hostname(hostname: str) -> list[str]:
    timeout = httpx.Timeout(5.0, connect=3.0)
    headers = {"accept": "application/dns-json"}
    proxy = settings.http_proxy or None
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy,
            headers=headers,
            trust_env=False,
        ) as client:
            response = await client.get(
                "https://dns.google/resolve",
                params={"name": hostname, "type": "A"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    answers = data.get("Answer") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        return []

    hosts: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict) or answer.get("type") != 1:
            continue
        host = str(answer.get("data") or "").strip()
        if host:
            hosts.append(host)
    return hosts


def _resolved_host(result) -> str:
    if hasattr(result, "host"):
        return str(result.host)
    if isinstance(result, tuple) and len(result) >= 5:
        sockaddr = result[4]
        if isinstance(sockaddr, tuple) and sockaddr:
            return str(sockaddr[0])
    return ""


async def _is_blocked_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return True
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    if _is_blocked_address(hostname):
        return True
    try:
        ipaddress.ip_address(hostname)
        return False
    except ValueError:
        pass
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return True
    resolved = await _resolve_hostname(hostname, port)
    if not resolved:
        return True
    needs_public_dns_check = False
    for result in resolved:
        host = _resolved_host(result)
        if _is_proxy_fake_ip_address(host):
            needs_public_dns_check = True
            continue
        if _is_blocked_address(host):
            return True
    if needs_public_dns_check:
        public_hosts = await _resolve_public_hostname(hostname)
        if not public_hosts:
            return True
        return any(_is_blocked_address(host) for host in public_hosts)
    return False


def _is_blocked_search_result_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return True
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    if _is_blocked_address(hostname):
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    try:
        parsed.port
    except ValueError:
        return True
    return False


async def search_web(
    query: str,
    *,
    max_results: int = 3,
    diagnostics: list[dict] | None = None,
    provider: str | None = None,
) -> list[dict[str, str]]:
    """Return lightweight web search snippets for LLM grounding."""
    term = _truncate_text(query.strip(), MAX_SEARCH_QUERY_CHARS)
    if not term:
        return []

    provider_override = provider is not None
    selected_provider = (provider or settings.web_search_provider).strip().lower()
    if selected_provider not in {"auto", "tavily", "html"}:
        selected_provider = settings.web_search_provider.strip().lower() or "html"
    timeout = httpx.Timeout(8.0, connect=4.0)
    proxy = settings.http_proxy or None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        proxy=proxy,
        headers=headers,
        trust_env=False,
    ) as client:
        if selected_provider in {"auto", "tavily"}:
            if not settings.tavily_api_key.strip():
                _append_missing_tavily_key_diagnostic(diagnostics)
                if (
                    provider_override and selected_provider == "tavily"
                ) or not settings.web_search_fallback_html:
                    _sort_provider_diagnostics(diagnostics)
                    return []
            else:
                tavily_results = await _try_search_provider(
                    "tavily",
                    _search_tavily,
                    client,
                    term,
                    max_results=max_results,
                    diagnostics=diagnostics,
                )
                if (
                    tavily_results
                    or (provider_override and selected_provider == "tavily")
                    or not settings.web_search_fallback_html
                ):
                    _sort_provider_diagnostics(diagnostics)
                    return tavily_results

        return await _search_html_providers(
            client,
            term,
            max_results=max_results,
            diagnostics=diagnostics,
        )


def _append_missing_tavily_key_diagnostic(diagnostics: list[dict] | None) -> None:
    if diagnostics is None:
        return
    diagnostics.append(
        {
            "provider": "tavily",
            "status": "failed",
            "error": "missing_api_key",
            "message": "TAVILY_API_KEY is not configured",
            "proxy_configured": bool(settings.http_proxy.strip()),
        }
    )


async def _search_html_providers(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: list[dict] | None = None,
) -> list[dict[str, str]]:
    combined: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    provider_tasks = [
        asyncio.create_task(
            _try_search_provider(
                provider,
                searcher,
                client,
                query,
                max_results=max_results,
                diagnostics=diagnostics,
            )
        )
        for provider, searcher in (
            ("duckduckgo", _search_duckduckgo),
            ("yahoo", _search_yahoo),
            ("sogou", _search_sogou),
        )
    ]
    try:
        for provider_task in asyncio.as_completed(provider_tasks):
            provider_results = await provider_task
            for result in provider_results:
                url = (result.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                combined.append(result)
                if len(combined) >= max_results:
                    await _cancel_pending_tasks(provider_tasks)
                    _sort_provider_diagnostics(diagnostics)
                    return combined
    finally:
        await _cancel_pending_tasks(provider_tasks)
    _sort_provider_diagnostics(diagnostics)
    return combined


async def _try_search_provider(
    provider: str,
    searcher,
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
    diagnostics: list[dict] | None = None,
) -> list[dict[str, str]]:
    try:
        results = await searcher(client, query, max_results=max_results)
    except Exception as exc:
        logger.debug(f"联网搜索源 {provider} 查询失败，继续尝试备用源: {exc}")
        if diagnostics is not None:
            diagnostics.append(
                {
                    "provider": provider,
                    "status": "failed",
                    "error": exc.__class__.__name__,
                    "message": _truncate_text(str(exc), 240) or "搜索源请求失败",
                    "proxy_configured": bool(settings.http_proxy.strip()),
                }
            )
        return []
    if diagnostics is not None:
        diagnostics.append(
            {
                "provider": provider,
                "status": "success" if results else "empty",
                "result_count": len(results),
                "message": "搜索源返回结果" if results else "搜索源返回空结果",
                "proxy_configured": bool(settings.http_proxy.strip()),
            }
        )
    return results


async def _search_duckduckgo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
    )
    response.raise_for_status()

    parser = _DuckDuckGoResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _search_tavily(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.post(
        "https://api.tavily.com/search",
        json={
            "query": query,
            "search_depth": settings.tavily_search_depth.strip() or "basic",
            "max_results": max_results,
            "include_answer": False,
        },
        headers={"Authorization": f"Bearer {settings.tavily_api_key.strip()}"},
    )
    response.raise_for_status()
    payload = response.json()
    raw_results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(raw_results, list):
        return []

    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "snippet": str(
                    item.get("content") or item.get("snippet") or ""
                ).strip(),
            }
        )
    return await _normalize_search_results(
        results,
        max_results=max_results,
    )


async def _search_sogou(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.get(
        "https://www.sogou.com/web",
        params={"query": query},
    )
    response.raise_for_status()

    parser = _SogouResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _search_yahoo(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int,
) -> list[dict[str, str]]:
    response = await client.get(
        "https://search.yahoo.com/search",
        params={"p": query},
    )
    response.raise_for_status()

    parser = _YahooResultParser()
    parser.feed(response.text)
    return await _normalize_search_results(
        parser.results,
        max_results=max_results,
    )


async def _normalize_search_results(
    results: list[dict[str, str]],
    *,
    max_results: int,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for result in results:
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        if (
            not title
            or not url
            or url in seen_urls
            or _is_blocked_search_result_url(url)
        ):
            continue
        seen_urls.add(url)
        normalized.append(
            {
                "title": _truncate_text(title, MAX_SEARCH_TITLE_CHARS),
                "url": url,
                "snippet": _truncate_text(
                    (result.get("snippet") or "").strip(),
                    MAX_SEARCH_SNIPPET_CHARS,
                ),
            }
        )
        if len(normalized) >= max_results:
            break
    return normalized


async def fetch_web_page(
    url: str,
    *,
    max_chars: int = 4000,
    max_bytes: int = 256_000,
) -> dict[str, str]:
    """Fetch a public web page and return cleaned text for LLM grounding."""
    normalized_url = url.strip()
    if await _is_blocked_url(normalized_url):
        return {
            "url": normalized_url,
            "title": "",
            "content": "",
            "error": "blocked_url",
            "message": "URL 不允许访问",
        }

    timeout = httpx.Timeout(8.0, connect=4.0)
    proxy = settings.http_proxy or None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            proxy=proxy,
            headers=headers,
            trust_env=False,
        ) as client:
            async with client.stream("GET", normalized_url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not _is_supported_content_type(content_type):
                    return {
                        "url": normalized_url,
                        "title": "",
                        "content": "",
                        "error": "unsupported_content_type",
                        "message": "仅支持读取文本网页",
                    }

                charset = _charset_from_content_type(content_type)
                body = bytearray()
                limit = max(0, max_bytes)
                async for chunk in response.aiter_bytes():
                    remaining = limit - len(body)
                    if remaining <= 0:
                        break
                    body.extend(chunk[:remaining])
                    if len(body) >= limit:
                        break
    except Exception as exc:
        return {
            "url": normalized_url,
            "title": "",
            "content": "",
            "error": "fetch_failed",
            "message": str(exc),
        }

    parser = _ReadableHTMLParser()
    parser.feed(_decode_body(bytes(body), charset))
    content = _truncate_text(parser.content, max_chars)
    return {
        "url": normalized_url,
        "title": parser.title,
        "content": content,
    }
