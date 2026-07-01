import httpx
import pytest

from app.services.bilibili_favorites import (
    clean_bilibili_favorite_resources,
    get_all_bilibili_favorite_videos,
    get_bilibili_favorite_content,
    get_bilibili_user_favorites,
    move_bilibili_favorite_resources,
)


class FakeBilibiliFavoriteClient:
    def __init__(self, *, get_payloads=None, post_payloads=None):
        self.get_payloads = list(get_payloads or [])
        self.post_payloads = list(post_payloads or [])
        self.get_calls = []
        self.post_calls = []

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        payload = self.get_payloads.pop(0)
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        payload = self.post_payloads.pop(0)
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))


def parse_response(response, _action):
    return response.json()


@pytest.mark.asyncio
async def test_get_user_favorites_requires_mid_and_returns_list():
    client = FakeBilibiliFavoriteClient(
        get_payloads=[
            {
                "code": 0,
                "data": {"list": [{"id": 1, "title": "默认收藏夹"}]},
            }
        ]
    )

    result = await get_bilibili_user_favorites(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        parse_json_response=parse_response,
        mid="42",
    )

    assert result == [{"id": 1, "title": "默认收藏夹"}]
    url, kwargs = client.get_calls[0]
    assert url.endswith("/x/v3/fav/folder/created/list-all")
    assert kwargs["params"] == {"up_mid": "42"}
    assert kwargs["cookies"] == {"SESSDATA": "sess"}

    with pytest.raises(Exception, match="未指定用户 ID"):
        await get_bilibili_user_favorites(
            client=client,
            base_url="https://api.bilibili.com",
            cookies={},
            parse_json_response=parse_response,
            mid=None,
        )


@pytest.mark.asyncio
async def test_get_all_favorite_videos_uses_paged_content_loader():
    calls = []

    async def load_content(media_id, *, pn, ps):
        calls.append((media_id, pn, ps))
        return {
            "medias": [{"id": pn}],
            "has_more": pn < 2,
        }

    result = await get_all_bilibili_favorite_videos(
        media_id=7,
        load_content=load_content,
        sleep=lambda _seconds: None,
    )

    assert result == [{"id": 1}, {"id": 2}]
    assert calls == [(7, 1, 20), (7, 2, 20)]


@pytest.mark.asyncio
async def test_favorite_content_move_and_clean_call_expected_bilibili_endpoints():
    client = FakeBilibiliFavoriteClient(
        get_payloads=[
            {
                "code": 0,
                "data": {
                    "info": {"id": 10},
                    "medias": [{"id": 100}],
                    "has_more": False,
                },
            }
        ],
        post_payloads=[
            {"code": 0, "data": {"moved": 2}},
            {"code": 0, "data": {"cleaned": 1}},
        ],
    )

    content = await get_bilibili_favorite_content(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        parse_json_response=parse_response,
        media_id=10,
        pn=3,
        ps=99,
    )
    moved = await move_bilibili_favorite_resources(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bili_jct="csrf",
        dedeuserid="42",
        src_media_id=10,
        tar_media_id=11,
        resources=["100:2", "101:2"],
    )
    cleaned = await clean_bilibili_favorite_resources(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={"SESSDATA": "sess"},
        bili_jct="csrf",
        media_id=10,
    )

    assert content == {"info": {"id": 10}, "medias": [{"id": 100}], "has_more": False}
    assert moved == {"moved": 2}
    assert cleaned == {"cleaned": 1}
    assert client.get_calls[0][1]["params"] == {
        "media_id": 10,
        "pn": 3,
        "ps": 20,
        "platform": "web",
    }
    assert client.post_calls[0][0].endswith("/x/v3/fav/resource/move")
    assert client.post_calls[0][1]["data"] == {
        "src_media_id": 10,
        "tar_media_id": 11,
        "resources": "100:2,101:2",
        "csrf": "csrf",
        "mid": "42",
    }
    assert client.post_calls[1][0].endswith("/x/v3/fav/resource/clean")
    assert client.post_calls[1][1]["data"] == {"media_id": 10, "csrf": "csrf"}


@pytest.mark.asyncio
async def test_move_and_clean_require_csrf_token():
    client = FakeBilibiliFavoriteClient()

    with pytest.raises(Exception, match="缺少 bili_jct"):
        await move_bilibili_favorite_resources(
            client=client,
            base_url="https://api.bilibili.com",
            cookies={},
            bili_jct=None,
            dedeuserid=None,
            src_media_id=1,
            tar_media_id=2,
            resources=["100:2"],
        )

    assert await move_bilibili_favorite_resources(
        client=client,
        base_url="https://api.bilibili.com",
        cookies={},
        bili_jct="csrf",
        dedeuserid=None,
        src_media_id=1,
        tar_media_id=2,
        resources=[],
    ) == {"moved": 0}

    with pytest.raises(Exception, match="缺少 bili_jct"):
        await clean_bilibili_favorite_resources(
            client=client,
            base_url="https://api.bilibili.com",
            cookies={},
            bili_jct=None,
            media_id=1,
        )
