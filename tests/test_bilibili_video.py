import httpx
import pytest

from app.services.bilibili_video import (
    get_bilibili_audio_url,
    get_bilibili_player_info,
    get_bilibili_video_info,
    get_bilibili_video_summary,
)


class FakeBilibiliVideoClient:
    def __init__(self, *, get_payloads):
        self.get_payloads = list(get_payloads)
        self.get_calls = []

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        payload = self.get_payloads.pop(0)
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))


class FakeWbiSigner:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.sign_calls = []

    async def sign(self, params, cookies=None):
        self.sign_calls.append((dict(params), cookies))
        if self.fail:
            raise Exception("sign failed")
        return {**params, "w_rid": "signed"}


@pytest.mark.asyncio
async def test_video_info_fetches_view_payload():
    client = FakeBilibiliVideoClient(
        get_payloads=[{"code": 0, "message": "OK", "data": {"bvid": "BV1"}}]
    )

    result = await get_bilibili_video_info(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bvid="BV1",
    )

    assert result == {"bvid": "BV1"}
    url, kwargs = client.get_calls[0]
    assert url.endswith("/x/web-interface/view")
    assert kwargs["params"] == {"bvid": "BV1"}
    assert kwargs["cookies"] == {"SESSDATA": "sess"}


@pytest.mark.asyncio
async def test_video_summary_signs_params_and_returns_none_on_api_failure():
    signer = FakeWbiSigner()
    client = FakeBilibiliVideoClient(
        get_payloads=[
            {"code": 0, "message": "OK", "data": {"summary": "ok"}},
            {"code": -1, "message": "denied"},
        ]
    )

    result = await get_bilibili_video_summary(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bvid="BV1",
        cid=7,
        up_mid=42,
        wbi_signer=signer,
    )
    failed = await get_bilibili_video_summary(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bvid="BV2",
        cid=8,
        wbi_signer=signer,
    )

    assert result == {"summary": "ok"}
    assert failed is None
    assert signer.sign_calls[0] == (
        {"bvid": "BV1", "cid": 7, "up_mid": 42},
        {"SESSDATA": "sess"},
    )
    assert client.get_calls[0][0].endswith("/x/web-interface/view/conclusion/get")
    assert client.get_calls[0][1]["params"]["w_rid"] == "signed"


@pytest.mark.asyncio
async def test_player_info_uses_wbi_then_falls_back_to_legacy_endpoint():
    signer = FakeWbiSigner(fail=True)
    client = FakeBilibiliVideoClient(
        get_payloads=[{"code": 0, "message": "OK", "data": {"subtitle": {}}}]
    )

    result = await get_bilibili_player_info(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bvid="BV1",
        cid=7,
        aid=9,
        wbi_signer=signer,
    )

    assert result == {"subtitle": {}}
    assert signer.sign_calls == [
        ({"bvid": "BV1", "cid": 7, "aid": 9}, {"SESSDATA": "sess"})
    ]
    url, kwargs = client.get_calls[0]
    assert url.endswith("/x/player/v2")
    assert kwargs["params"] == {"bvid": "BV1", "cid": 7, "aid": 9}


@pytest.mark.asyncio
async def test_audio_url_uses_wbi_payload_and_legacy_fallback():
    signer = FakeWbiSigner()
    client = FakeBilibiliVideoClient(
        get_payloads=[
            {
                "code": -1,
                "message": "wbi denied",
                "data": {},
            },
            {
                "code": 0,
                "message": "OK",
                "data": {"durl": [{"url": "https://audio.example/legacy.mp4"}]},
            },
        ]
    )

    result = await get_bilibili_audio_url(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bvid="BV1",
        cid=7,
        wbi_signer=signer,
    )

    assert result == "https://audio.example/legacy.mp4"
    assert client.get_calls[0][0].endswith("/x/player/wbi/playurl")
    assert client.get_calls[1][0].endswith("/x/player/playurl")
    assert signer.sign_calls[0] == (
        {"bvid": "BV1", "cid": 7, "fnval": 16, "fnver": 0, "fourk": 1},
        {"SESSDATA": "sess"},
    )
