import httpx
import pytest


def test_bilibili_service_from_cookies_maps_common_cookie_names(monkeypatch):
    from app.services import bilibili

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(bilibili.httpx, "AsyncClient", FakeAsyncClient)

    service = bilibili.bilibili_service_from_cookies(
        {
            "SESSDATA": "sess",
            "bili_jct": "csrf",
            "DedeUserID": "42",
            "ignored": "value",
        }
    )

    assert service.sessdata == "sess"
    assert service.bili_jct == "csrf"
    assert service.dedeuserid == "42"


def test_bilibili_service_from_cookies_accepts_lowercase_aliases(monkeypatch):
    from app.services import bilibili

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(bilibili.httpx, "AsyncClient", FakeAsyncClient)

    service = bilibili.bilibili_service_from_cookies(
        {
            "sessdata": "sess",
            "bili_jct": "csrf",
            "dedeuserid": "42",
        }
    )

    assert service._get_cookies() == {
        "SESSDATA": "sess",
        "bili_jct": "csrf",
        "DedeUserID": "42",
    }


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


@pytest.mark.asyncio
async def test_bilibili_service_mixins_delegate_media_calls(monkeypatch):
    from app.services import bilibili_service_mixins as mixins
    from app.services.bilibili import BilibiliService

    captured = {}

    async def fake_download_audio(client, audio_url, file_path, *, headers, cookies):
        captured["audio"] = {
            "client": client,
            "audio_url": audio_url,
            "file_path": file_path,
            "headers": headers,
            "cookies": cookies,
        }
        return True

    monkeypatch.setattr(
        mixins,
        "download_bilibili_audio_to_file",
        fake_download_audio,
    )
    monkeypatch.setattr(
        mixins,
        "normalize_bilibili_media_url",
        lambda url: f"https:{url}" if url.startswith("//") else url,
    )
    monkeypatch.setattr(
        mixins,
        "subtitle_text_from_payload",
        lambda payload: "|".join(item["content"] for item in payload["body"]),
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_args"] = args
            captured["client_kwargs"] = kwargs

        async def get(self, url):
            captured["subtitle_url"] = url
            return type(
                "Response",
                (),
                {"json": lambda self: {"body": [{"content": "第一句"}]}},
            )()

        async def aclose(self):
            pass

    monkeypatch.setattr("app.services.bilibili.httpx.AsyncClient", FakeAsyncClient)

    service = BilibiliService(sessdata="sess", bili_jct="csrf", dedeuserid="42")

    assert await service.download_subtitle("//subtitle.example/path.json") == "第一句"
    assert await service.download_audio_to_file("https://audio.example/a.m4s", "a.m4s")

    assert captured["subtitle_url"] == "https://subtitle.example/path.json"
    assert captured["audio"]["client"] is service.client
    assert captured["audio"]["headers"] == service.HEADERS
    assert captured["audio"]["cookies"] == {
        "SESSDATA": "sess",
        "bili_jct": "csrf",
        "DedeUserID": "42",
    }
