import pytest

from app.services.wbi import WbiSigner


class FakeNavResponse:
    def json(self):
        return {
            "code": -101,
            "message": "账号未登录",
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png",
                }
            },
        }


class FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, *args, **kwargs):
        return FakeNavResponse()


@pytest.mark.asyncio
async def test_wbi_signer_uses_wbi_img_from_logged_out_nav_payload(monkeypatch):
    monkeypatch.setattr("app.services.wbi.httpx.AsyncClient", FakeAsyncClient)
    signer = WbiSigner()

    signed = await signer.sign({"bvid": "BV1", "cid": 7}, cookies=None)

    assert signed["bvid"] == "BV1"
    assert signed["cid"] == "7"
    assert isinstance(signed["wts"], int)
    assert len(signed["w_rid"]) == 32
