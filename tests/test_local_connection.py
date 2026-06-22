import re

import pytest

from app.routers.local_connection import _qr_png_bytes, _select_lan_ipv4_address


def test_select_lan_ipv4_address_ignores_proxy_and_link_local_ranges():
    assert (
        _select_lan_ipv4_address(
            [
                "198.18.0.1",
                "169.254.148.111",
                "192.168.1.198",
            ]
        )
        == "192.168.1.198"
    )


@pytest.mark.asyncio
async def test_lan_address_returns_detected_local_urls(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.local_connection._get_lan_ipv4_address",
        lambda: "192.168.1.200",
    )

    response = await client.get("/local-connection/lan-address")

    assert response.status_code == 200
    data = response.json()
    assert data["host"] == "192.168.1.200"
    assert data["api_url"] == "http://192.168.1.200:8000"
    assert data["frontend_url"] == "http://192.168.1.200:3000"
    assert (
        data["connect_page_url"]
        == "http://192.168.1.200:8000/local-connection/mobile-connect?api=http%3A%2F%2F192.168.1.200%3A8000"
    )
    assert (
        data["qr_image_url"]
        == "http://192.168.1.200:8000/local-connection/mobile-connect.png?api=http%3A%2F%2F192.168.1.200%3A8000"
    )
    assert data["qr_data_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_lan_address_returns_nulls_when_no_local_ip(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.local_connection._get_lan_ipv4_address",
        lambda: None,
    )

    response = await client.get("/local-connection/lan-address")

    assert response.status_code == 200
    assert response.json() == {
        "host": None,
        "api_url": None,
        "frontend_url": None,
        "qr_url": None,
        "connect_page_url": None,
        "qr_image_url": None,
        "qr_data_url": None,
    }


@pytest.mark.asyncio
async def test_mobile_connect_png_returns_qr_image(client):
    response = await client.get(
        "/local-connection/mobile-connect.png",
        params={"api": "http://192.168.1.200:8000"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_qr_png_generation_is_cached(monkeypatch):
    calls = 0

    class FakeImage:
        def save(self, output, format):
            output.write(b"png-bytes")

    def fake_make(value):
        nonlocal calls
        calls += 1
        return FakeImage()

    monkeypatch.setattr("app.routers.local_connection.qrcode.make", fake_make)
    _qr_png_bytes.cache_clear()
    try:
        assert _qr_png_bytes("zhikuyun://connect?api=test") == b"png-bytes"
        assert _qr_png_bytes("zhikuyun://connect?api=test") == b"png-bytes"
    finally:
        _qr_png_bytes.cache_clear()

    assert calls == 1


@pytest.mark.asyncio
async def test_mobile_connect_page_contains_deep_link_qr(client):
    response = await client.get(
        "/local-connection/mobile-connect",
        params={"api": "http://192.168.1.200:8000"},
    )

    assert response.status_code == 200
    html = response.text
    assert "zhikuyun://connect?api=" in html
    assert "data:image/png;base64," in html
    assert "http://192.168.1.200:8000" in html
    assert re.search(r"<img[^>]+alt=\"手机连接二维码\"", html)


@pytest.mark.asyncio
async def test_mobile_connect_page_rejects_public_api_url(client):
    response = await client.get(
        "/local-connection/mobile-connect",
        params={"api": "http://example.com:8000"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_private_network_preflight_allows_lan_access(client):
    response = await client.options(
        "/system-auth/login",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-private-network"] == "true"
