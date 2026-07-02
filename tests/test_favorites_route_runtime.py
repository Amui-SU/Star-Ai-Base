import pytest
from fastapi import HTTPException

from app.services.favorites_route_runtime import (
    list_all_legacy_favorite_videos,
    list_legacy_favorite_folders,
    list_legacy_favorite_videos,
)


class FakeLegacyFavoritesService:
    def __init__(self):
        self.closed = False
        self.favorite_content_calls = []
        self.user_favorite_mid = None

    async def get_user_favorites(self, mid):
        self.user_favorite_mid = mid
        return [
            {"id": 10, "title": "默认收藏夹", "media_count": 3, "attr": 1},
            {"id": 11, "title": "学习", "media_count": 2},
        ]

    async def get_favorite_content(self, media_id, pn, ps):
        self.favorite_content_calls.append((media_id, pn, ps))
        return {
            "info": {"id": media_id, "title": "学习"},
            "has_more": True,
            "medias": [
                {
                    "bvid": "BV1",
                    "title": "Video One",
                    "cover": "cover.jpg",
                    "duration": 90,
                    "upper": {"name": "Uploader"},
                    "cnt_info": {"play": 123},
                    "intro": "Intro",
                },
                {"bv_id": "BV2", "title": "Video Two"},
            ],
        }

    async def get_all_favorite_videos(self, media_id):
        return [
            {
                "bvid": "BVVALID",
                "title": "Valid",
                "cover": "valid.jpg",
                "duration": 10,
                "upper": {"name": "Uploader"},
                "ugc": {"first_cid": 1001},
            },
            {"bvid": "BVLOST", "title": "已失效视频"},
            {"bv_id": "BVDELETED", "title": "Deleted", "attr": 9},
            {"title": "Missing bvid"},
        ]

    async def close(self):
        self.closed = True


async def _fake_session(_session_id):
    return {
        "cookies": {"DedeUserID": "4242"},
        "user_info": {},
    }


@pytest.mark.asyncio
async def test_legacy_favorite_folder_runtime_marks_default_and_closes_service():
    fake_service = FakeLegacyFavoritesService()

    folders = await list_legacy_favorite_folders(
        "sid",
        get_session_func=_fake_session,
        service_from_cookies=lambda _cookies, _service_cls: fake_service,
    )

    assert fake_service.user_favorite_mid == "4242"
    assert [folder.media_id for folder in folders] == [10, 11]
    assert folders[0].is_default is True
    assert folders[1].is_default is False
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_legacy_favorite_video_runtime_maps_paged_video_payload_and_closes():
    fake_service = FakeLegacyFavoritesService()

    result = await list_legacy_favorite_videos(
        11,
        session_id="sid",
        page=2,
        page_size=20,
        get_session_func=_fake_session,
        service_from_cookies=lambda _cookies, _service_cls: fake_service,
    )

    assert fake_service.favorite_content_calls == [(11, 2, 20)]
    assert result["folder_info"] == {"id": 11, "title": "学习"}
    assert result["has_more"] is True
    assert result["videos"][0] == {
        "bvid": "BV1",
        "title": "Video One",
        "cover": "cover.jpg",
        "duration": 90,
        "owner": "Uploader",
        "play_count": 123,
        "intro": "Intro",
        "is_selected": True,
    }
    assert result["videos"][1]["bvid"] == "BV2"
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_legacy_all_favorite_videos_runtime_filters_invalid_media_and_closes():
    fake_service = FakeLegacyFavoritesService()

    result = await list_all_legacy_favorite_videos(
        10,
        session_id="sid",
        get_session_func=_fake_session,
        service_from_cookies=lambda _cookies, _service_cls: fake_service,
    )

    assert result == {
        "total": 1,
        "videos": [
            {
                "bvid": "BVVALID",
                "title": "Valid",
                "cover": "valid.jpg",
                "duration": 10,
                "owner": "Uploader",
                "cid": 1001,
            }
        ],
    }
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_legacy_favorite_runtime_rejects_missing_session_as_401():
    async def missing_session(_session_id):
        return None

    with pytest.raises(HTTPException) as exc_info:
        await list_legacy_favorite_folders("missing", get_session_func=missing_session)

    assert exc_info.value.status_code == 401
