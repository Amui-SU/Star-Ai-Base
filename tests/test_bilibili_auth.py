import httpx
import pytest

from app.services.bilibili_auth import (
    generate_bilibili_qrcode,
    get_bilibili_user_info,
    poll_bilibili_qrcode_status,
)
from app.services.bilibili_responses import parse_bilibili_json_response


class FakeBilibiliAuthClient:
    def __init__(self, *, get_results):
        self.get_results = list(get_results)
        self.get_calls = []

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        result = self.get_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def json_response(url, payload, *, cookies=None):
    response = httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    if cookies:
        response.cookies.update(cookies)
    return response


@pytest.mark.asyncio
async def test_generate_qrcode_retries_transient_error_and_returns_base64_image():
    client = FakeBilibiliAuthClient(
        get_results=[
            httpx.ConnectTimeout("timeout"),
            json_response(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                {
                    "code": 0,
                    "message": "OK",
                    "data": {
                        "qrcode_key": "qr-key",
                        "url": "https://passport.bilibili.com/scan",
                    },
                },
            ),
        ]
    )

    result = await generate_bilibili_qrcode(
        client=client,
        passport_url="https://passport.bilibili.com",
        parse_json_response=parse_bilibili_json_response,
        sleep=lambda _seconds: None,
    )

    assert len(client.get_calls) == 2
    assert result["qrcode_key"] == "qr-key"
    assert result["qrcode_url"] == "https://passport.bilibili.com/scan"
    assert result["qrcode_image_base64"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_poll_qrcode_status_extracts_confirmed_cookies_from_response_and_url():
    url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    client = FakeBilibiliAuthClient(
        get_results=[
            json_response(
                url,
                {
                    "code": 0,
                    "message": "OK",
                    "data": {
                        "code": 0,
                        "message": "success",
                        "url": (
                            "https://www.bilibili.com/?"
                            "SESSDATA=url-sess&bili_jct=url-csrf&DedeUserID=42"
                        ),
                        "refresh_token": "refresh-token",
                    },
                },
                cookies={"SESSDATA": "jar-sess"},
            )
        ]
    )

    result = await poll_bilibili_qrcode_status(
        client=client,
        passport_url="https://passport.bilibili.com",
        parse_json_response=parse_bilibili_json_response,
        qrcode_key="qr-key",
    )

    assert result == {
        "status": "confirmed",
        "message": "登录成功",
        "cookies": {
            "SESSDATA": "url-sess",
            "bili_jct": "url-csrf",
            "DedeUserID": "42",
        },
        "refresh_token": "refresh-token",
    }
    assert client.get_calls[0][1]["params"] == {"qrcode_key": "qr-key"}


@pytest.mark.asyncio
async def test_poll_qrcode_status_maps_waiting_state():
    client = FakeBilibiliAuthClient(
        get_results=[
            json_response(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                {
                    "code": 0,
                    "message": "OK",
                    "data": {"code": 86101, "message": "not scanned"},
                },
            )
        ]
    )

    result = await poll_bilibili_qrcode_status(
        client=client,
        passport_url="https://passport.bilibili.com",
        parse_json_response=parse_bilibili_json_response,
        qrcode_key="qr-key",
    )

    assert result == {"status": "waiting", "message": "等待扫码"}


@pytest.mark.asyncio
async def test_get_user_info_raises_when_nav_api_fails():
    client = FakeBilibiliAuthClient(
        get_results=[
            json_response(
                "https://api.bilibili.com/x/web-interface/nav",
                {"code": -101, "message": "not logged in"},
            )
        ]
    )

    with pytest.raises(Exception, match="获取用户信息失败: not logged in"):
        await get_bilibili_user_info(
            client=client,
            base_url="https://api.bilibili.com",
            cookies={"SESSDATA": "sess"},
        )
