"""Authentication and user identity helpers for Bilibili."""

import asyncio
import base64
import io
import urllib.parse
from collections.abc import Awaitable, Callable
from typing import Any, Mapping

import httpx
import qrcode


ParseJsonResponse = Callable[[httpx.Response, str], dict[str, Any]]


async def _maybe_sleep(
    sleep: Callable[[float], Awaitable[Any] | Any],
    seconds: float,
) -> None:
    maybe_awaitable = sleep(seconds)
    if hasattr(maybe_awaitable, "__await__"):
        await maybe_awaitable


def _qrcode_image_base64(qrcode_url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qrcode_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


async def generate_bilibili_qrcode(
    *,
    client: Any,
    passport_url: str,
    parse_json_response: ParseJsonResponse,
    sleep: Callable[[float], Awaitable[Any] | Any] = asyncio.sleep,
) -> dict[str, Any]:
    """Generate a Bilibili login QR code payload."""
    url = f"{passport_url}/x/passport-login/web/qrcode/generate"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.get(url)
            data = parse_json_response(response, "生成二维码")
            break
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.TransportError,
        ) as exc:
            last_error = exc
            if attempt == 2:
                raise Exception("连接 B站二维码接口超时或网络异常，请稍后重试") from exc
            await _maybe_sleep(sleep, 0.6 * (attempt + 1))
    else:
        raise last_error or Exception("连接 B站二维码接口失败")

    if data["code"] != 0:
        raise Exception(f"生成二维码失败: {data['message']}")

    qrcode_key = data["data"]["qrcode_key"]
    qrcode_url = data["data"]["url"]
    return {
        "qrcode_key": qrcode_key,
        "qrcode_url": qrcode_url,
        "qrcode_image_base64": _qrcode_image_base64(qrcode_url),
    }


def _cookies_from_confirmed_qrcode(response: httpx.Response, url_str: str) -> dict:
    cookies = {}
    for cookie in response.cookies.jar:
        cookies[cookie.name] = cookie.value

    if "SESSDATA=" in url_str:
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url_str).query)
        for key in ["SESSDATA", "bili_jct", "DedeUserID"]:
            if key in parsed:
                cookies[key] = parsed[key][0]

    return cookies


async def poll_bilibili_qrcode_status(
    *,
    client: Any,
    passport_url: str,
    parse_json_response: ParseJsonResponse,
    qrcode_key: str,
) -> dict[str, Any]:
    """Poll Bilibili QR code login status."""
    url = f"{passport_url}/x/passport-login/web/qrcode/poll"
    try:
        response = await client.get(url, params={"qrcode_key": qrcode_key})
        data = parse_json_response(response, "轮询二维码状态")
    except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
        raise Exception(
            "连接 B站二维码状态接口超时或网络异常，请重新获取二维码"
        ) from exc

    if data["code"] != 0:
        raise Exception(f"轮询二维码状态失败: {data['message']}")

    inner_code = data["data"]["code"]
    message = data["data"]["message"]
    status_map = {
        86101: ("waiting", "等待扫码"),
        86090: ("scanned", "已扫码，等待确认"),
        86038: ("expired", "二维码已过期"),
        0: ("confirmed", "登录成功"),
    }
    status, msg = status_map.get(inner_code, ("unknown", message))

    result: dict[str, Any] = {"status": status, "message": msg}
    if status == "confirmed":
        result["cookies"] = _cookies_from_confirmed_qrcode(
            response,
            data["data"].get("url", ""),
        )
        result["refresh_token"] = data["data"].get("refresh_token", "")

    return result


async def get_bilibili_user_info(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
) -> dict[str, Any]:
    """Fetch the current Bilibili user identity payload."""
    url = f"{base_url}/x/web-interface/nav"
    response = await client.get(url, cookies=dict(cookies))
    data = response.json()

    if data["code"] != 0:
        raise Exception(f"获取用户信息失败: {data['message']}")

    return data["data"]
