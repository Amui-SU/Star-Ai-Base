import base64
import html
import ipaddress
import io
import socket
import urllib.parse
from functools import lru_cache

import qrcode
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

router = APIRouter(prefix="/local-connection", tags=["本地连接"])


def _is_private_ipv4(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if ip.version != 4 or ip.is_loopback or ip.is_link_local:
        return False
    return (
        value.startswith("10.")
        or value.startswith("192.168.")
        or any(value.startswith(f"172.{octet}.") for octet in range(16, 32))
    )


def _select_lan_ipv4_address(candidates: list[str]) -> str | None:
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_private_ipv4(candidate):
            return candidate
    return None


def _get_lan_ipv4_address() -> str | None:
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.append(probe.getsockname()[0])
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        candidates.extend(
            info[4][0] for info in socket.getaddrinfo(hostname, None, socket.AF_INET)
        )
    except OSError:
        pass

    return _select_lan_ipv4_address(candidates)


def _validate_local_api_url(api: str) -> str:
    parsed = urllib.parse.urlparse(api.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid API URL")

    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1"}:
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="API URL must use a local IP"
        ) from exc

    if not (ip.is_private or ip.is_loopback):
        raise HTTPException(status_code=400, detail="API URL must use a local IP")

    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


@lru_cache(maxsize=64)
def _qr_png_bytes(value: str) -> bytes:
    image = qrcode.make(value)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@lru_cache(maxsize=64)
def _qr_data_url(value: str) -> str:
    encoded = base64.b64encode(_qr_png_bytes(value)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _connect_deep_link(api_url: str) -> str:
    return f"zhikuyun://connect?api={urllib.parse.quote(api_url, safe='')}"


def _mobile_connect_url(api_url: str, suffix: str = "") -> str:
    return (
        f"{api_url}/local-connection/mobile-connect{suffix}"
        f"?api={urllib.parse.quote(api_url, safe='')}"
    )


@router.get("/lan-address")
async def lan_address() -> dict[str, str | None]:
    host = _get_lan_ipv4_address()
    if not host:
        return {
            "host": None,
            "api_url": None,
            "frontend_url": None,
            "qr_url": None,
            "connect_page_url": None,
            "qr_image_url": None,
            "qr_data_url": None,
        }

    api_url = f"http://{host}:8000"
    deep_link = _connect_deep_link(api_url)
    connect_page_url = _mobile_connect_url(api_url)
    qr_image_url = _mobile_connect_url(api_url, ".png")
    return {
        "host": host,
        "api_url": api_url,
        "frontend_url": f"http://{host}:3000",
        "qr_url": qr_image_url,
        "connect_page_url": connect_page_url,
        "qr_image_url": qr_image_url,
        "qr_data_url": _qr_data_url(deep_link),
    }


@router.get("/mobile-connect.png")
async def mobile_connect_png(api: str = Query(...)) -> Response:
    api_url = _validate_local_api_url(api)
    return Response(
        content=_qr_png_bytes(_connect_deep_link(api_url)),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/mobile-connect", response_class=HTMLResponse)
async def mobile_connect(api: str = Query(...)) -> HTMLResponse:
    api_url = _validate_local_api_url(api)
    deep_link = _connect_deep_link(api_url)
    qr_url = _qr_data_url(deep_link)
    safe_api = html.escape(api_url)
    safe_link = html.escape(deep_link)

    return HTMLResponse(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>智库云手机连接</title>
  <style>
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      background: #141413;
      color: #faf9f5;
      font-family: Inter, "Noto Sans SC", sans-serif;
    }}
    main {{
      width: min(420px, calc(100vw - 32px));
      display: grid;
      gap: 18px;
      text-align: center;
    }}
    img {{
      width: min(280px, 72vw);
      height: auto;
      margin: 0 auto;
      border-radius: 18px;
      background: #fff;
      padding: 14px;
    }}
    code {{
      display: block;
      overflow-wrap: anywhere;
      border: 1px solid #333230;
      border-radius: 12px;
      padding: 10px 12px;
      color: #dedbd4;
      background: #262624;
      font-size: 13px;
    }}
    p {{
      margin: 0;
      color: #a8a49c;
      line-height: 1.7;
    }}
  </style>
</head>
<body>
  <main>
    <h1>智库云手机连接</h1>
    <img src="{qr_url}" alt="手机连接二维码" />
    <p>用手机扫码打开智库云，或在 APK 的“连接设置”里填写下面的后端地址。</p>
    <code>{safe_api}</code>
    <code>{safe_link}</code>
  </main>
</body>
</html>"""
    )
