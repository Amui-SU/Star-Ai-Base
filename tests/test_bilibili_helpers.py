import pytest
import httpx

from app.services.bilibili_cookies import (
    normalize_bilibili_cookies,
    service_kwargs_from_cookies,
)
from app.services.bilibili_responses import parse_bilibili_json_response


def test_bilibili_cookie_helpers_accept_common_aliases():
    cookies = {
        "sessdata": "sess-lower",
        "bili_jct": "csrf",
        "Dedeuserid": "4242",
    }

    assert service_kwargs_from_cookies(cookies) == {
        "sessdata": "sess-lower",
        "bili_jct": "csrf",
        "dedeuserid": "4242",
    }
    assert normalize_bilibili_cookies(cookies) == {
        "SESSDATA": "sess-lower",
        "bili_jct": "csrf",
        "DedeUserID": "4242",
    }


def test_parse_bilibili_json_response_wraps_empty_or_non_json_body():
    response = httpx.Response(502, content=b"", request=httpx.Request("GET", "/api"))

    with pytest.raises(Exception) as exc_info:
        parse_bilibili_json_response(response, "Fetch data")

    message = str(exc_info.value)
    assert "Fetch data" in message
    assert "status=502" in message
    assert "EMPTY" in message
