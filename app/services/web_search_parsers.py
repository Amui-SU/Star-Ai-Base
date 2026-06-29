from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from app.services.web_page_fetcher import compact_text


class DuckDuckGoResultParser(HTMLParser):
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


class SogouResultParser(HTMLParser):
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
            self._current["title"] = compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "snippet" and tag in {"p", "div"}:
            self._current["snippet"] = compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "cite" and tag == "cite":
            cite = self._normalize_url(compact_text(" ".join(self._text_parts)))
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


class YahooResultParser(HTMLParser):
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
            self._current["title"] = compact_text(" ".join(self._text_parts))
            self._capture = None
            self._text_parts = []
        elif self._capture == "snippet" and tag == "p":
            self._current["snippet"] = compact_text(" ".join(self._text_parts))
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
