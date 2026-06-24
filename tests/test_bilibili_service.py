import httpx
import pytest


@pytest.mark.asyncio
async def test_qrcode_generation_retries_transient_connect_timeout(monkeypatch):
    from app.services import bilibili

    calls = {"count": 0}
    client_kwargs = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            client_kwargs.update(kwargs)

        async def get(self, url, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise httpx.ConnectTimeout("proxy timed out")
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "message": "OK",
                    "data": {
                        "qrcode_key": "qr-key",
                        "url": "https://account.bilibili.com/scan",
                    },
                },
            )

        async def aclose(self):
            pass

    monkeypatch.setattr(bilibili.httpx, "AsyncClient", FakeAsyncClient)

    service = bilibili.BilibiliService()
    try:
        result = await service.generate_qrcode()
    finally:
        await service.close()

    assert calls["count"] == 2
    assert client_kwargs["trust_env"] is False
    assert result["qrcode_key"] == "qr-key"
    assert result["qrcode_image_base64"].startswith("data:image/png;base64,")
