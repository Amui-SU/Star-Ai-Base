from collections.abc import Awaitable, Callable
from html.parser import HTMLParser
import re

import httpx

from app.config import settings


class ReadableHTMLParser(HTMLParser):
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
            self.title = compact_text(f"{self.title} {text}")
            return
        self._text_parts.append(text)

    @property
    def content(self) -> str:
        return compact_text(" ".join(self._text_parts))


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text: str, max_chars: int) -> str:
    limit = max(0, max_chars)
    if len(text) <= limit:
        return text
    truncated = text[:limit].strip()
    boundary = max(truncated.rfind(mark) for mark in "\u3002\uff01\uff1f!?\n")
    if boundary > 0:
        return truncated[: boundary + 1].strip()
    return truncated


def is_supported_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return (
        not normalized
        or normalized == "text/html"
        or normalized == "text/plain"
        or normalized.endswith("+html")
    )


def charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([^\s;]+)", content_type, re.IGNORECASE)
    if not match:
        return "utf-8"
    return match.group(1).strip("\"'") or "utf-8"


def decode_body(body: bytes, charset: str) -> str:
    try:
        return body.decode(charset, errors="ignore")
    except LookupError:
        return body.decode("utf-8", errors="ignore")


async def fetch_web_page(
    url: str,
    *,
    max_chars: int = 4000,
    max_bytes: int = 256_000,
    is_blocked_url_fn: Callable[[str], Awaitable[bool]],
) -> dict[str, str]:
    """Fetch a public web page and return cleaned text for LLM grounding."""
    normalized_url = url.strip()
    if await is_blocked_url_fn(normalized_url):
        return {
            "url": normalized_url,
            "title": "",
            "content": "",
            "error": "blocked_url",
            "message": "URL is not allowed",
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
                if not is_supported_content_type(content_type):
                    return {
                        "url": normalized_url,
                        "title": "",
                        "content": "",
                        "error": "unsupported_content_type",
                        "message": "Only text web pages are supported",
                    }

                charset = charset_from_content_type(content_type)
                body = bytearray()
                limit = max(0, max_bytes)
                async for chunk in response.aiter_bytes():
                    remaining = limit - len(body)
                    if remaining <= 0:
                        break
                    body.extend(chunk[:remaining])
                    if len(body) >= limit:
                        break
    except Exception:
        return {
            "url": normalized_url,
            "title": "",
            "content": "",
            "error": "fetch_failed",
            "message": "网页读取失败",
        }

    parser = ReadableHTMLParser()
    parser.feed(decode_body(bytes(body), charset))
    content = truncate_text(parser.content, max_chars)
    return {
        "url": normalized_url,
        "title": parser.title,
        "content": content,
    }
