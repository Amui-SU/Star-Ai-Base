import pytest
import httpx

from app.services.bilibili_cookies import (
    normalize_bilibili_cookies,
    service_kwargs_from_cookies,
)
from app.services.bilibili_responses import parse_bilibili_json_response
from app.services.bilibili_media import (
    normalize_bilibili_media_url,
    select_audio_url_from_playurl_payload,
    subtitle_text_from_payload,
)


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


def test_select_audio_url_prefers_highest_audio_under_asr_bandwidth_limit():
    payload = {
        "dash": {
            "audio": [
                {"bandwidth": 128000, "baseUrl": "https://audio.example/128.m4s"},
                {"bandWidth": "64000", "base_url": "https://audio.example/64.m4s"},
                {"bandwidth": 32000, "url": "https://audio.example/32.m4s"},
            ]
        }
    }

    assert (
        select_audio_url_from_playurl_payload(payload) == "https://audio.example/64.m4s"
    )


def test_select_audio_url_falls_back_to_lowest_audio_or_first_durl():
    assert (
        select_audio_url_from_playurl_payload(
            {
                "dash": {
                    "audio": [
                        {
                            "bandwidth": 192000,
                            "baseUrl": "https://audio.example/192.m4s",
                        },
                        {
                            "bandwidth": 128000,
                            "baseUrl": "https://audio.example/128.m4s",
                        },
                    ]
                }
            }
        )
        == "https://audio.example/128.m4s"
    )

    assert (
        select_audio_url_from_playurl_payload(
            {"durl": [{"url": "https://audio.example/legacy.mp4"}]}
        )
        == "https://audio.example/legacy.mp4"
    )


def test_subtitle_helpers_normalize_protocol_and_join_content():
    assert (
        normalize_bilibili_media_url("//subtitle.example/path.json")
        == "https://subtitle.example/path.json"
    )
    assert (
        subtitle_text_from_payload(
            {
                "body": [
                    {"content": "第一句"},
                    {"content": ""},
                    {"content": "第二句"},
                    {"from": 2.0},
                ]
            }
        )
        == "第一句\n第二句"
    )
