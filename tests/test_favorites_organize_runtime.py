from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.favorites_route_runtime import (
    clean_legacy_favorite_invalid_resources,
    execute_legacy_favorite_organization,
    preview_legacy_favorite_organization,
)


class FakeBilibiliService:
    def __init__(self):
        self.closed = False
        self.moves = []

    async def close(self):
        self.closed = True

    async def get_user_favorites(self, mid=None):
        return [
            {"id": 100, "title": "默认收藏夹", "media_count": 3},
            {"id": 200, "title": "Python", "media_count": 0},
        ]

    async def get_all_favorite_videos(self, media_id):
        assert media_id == 100
        return [
            {
                "bvid": "BVVALID0001",
                "title": "Valid Video",
                "id": "123",
                "type": "2",
                "attr": 0,
            },
            {
                "bvid": "BVDELETED01",
                "title": "已删除视频",
                "id": "124",
                "type": 2,
                "attr": 0,
            },
            {
                "bvid": "BVINVALIDID",
                "title": "Invalid Resource",
                "id": None,
                "type": 2,
                "attr": 0,
            },
        ]

    async def move_favorite_resources(self, **kwargs):
        self.moves.append(kwargs)

    async def clean_favorite_resources(self, folder_id):
        return {"folder_id": folder_id, "cleaned": 2}


async def fake_get_session(_session_id):
    return {
        "cookies": {"DedeUserID": "42"},
        "user_info": {"mid": "42"},
    }


def fake_service_from_cookies(_cookies, _service_cls):
    return FakeBilibiliService()


@pytest.mark.asyncio
async def test_preview_legacy_favorite_organization_filters_invalid_videos():
    result = await preview_legacy_favorite_organization(
        folder_id=999,
        session_id="sid",
        preview_response_class=lambda **kwargs: SimpleNamespace(**kwargs),
        preview_item_class=lambda **kwargs: SimpleNamespace(**kwargs),
        folder_info_class=lambda **kwargs: SimpleNamespace(**kwargs),
        get_session_func=fake_get_session,
        service_from_cookies=fake_service_from_cookies,
        service_cls=FakeBilibiliService,
        warning_logger=lambda _message: None,
    )

    assert result.default_folder_id == 100
    assert [folder.media_id for folder in result.folders] == [200]
    assert len(result.items) == 1
    assert result.items[0].bvid == "BVVALID0001"
    assert result.items[0].resource_id == 123
    assert result.items[0].resource_type == 2
    assert result.stats == {"total": 1, "matched": 0, "unmatched": 1}


@pytest.mark.asyncio
async def test_execute_legacy_favorite_organization_groups_moves_and_skips_default():
    service = FakeBilibiliService()

    result = await execute_legacy_favorite_organization(
        default_folder_id=100,
        moves=[
            {"resource_id": 1, "resource_type": 2, "target_folder_id": 100},
            {"resource_id": 2, "resource_type": 2, "target_folder_id": 200},
            {"resource_id": 3, "resource_type": 4, "target_folder_id": 200},
        ],
        session_id="sid",
        get_session_func=fake_get_session,
        service_from_cookies=lambda _cookies, _service_cls: service,
        service_cls=FakeBilibiliService,
    )

    assert result == {"message": "移动完成", "moved": 2, "groups": 1}
    assert service.moves == [
        {
            "src_media_id": 100,
            "tar_media_id": 200,
            "resources": ["2:2", "3:4"],
        }
    ]
    assert service.closed is True


@pytest.mark.asyncio
async def test_clean_legacy_favorite_invalid_resources_closes_service():
    service = FakeBilibiliService()

    result = await clean_legacy_favorite_invalid_resources(
        folder_id=100,
        session_id="sid",
        get_session_func=fake_get_session,
        service_from_cookies=lambda _cookies, _service_cls: service,
        service_cls=FakeBilibiliService,
    )

    assert result == {"message": "清理完成", "data": {"folder_id": 100, "cleaned": 2}}
    assert service.closed is True


@pytest.mark.asyncio
async def test_legacy_favorite_organize_rejects_missing_session():
    async def missing_session(_session_id):
        return None

    with pytest.raises(HTTPException) as exc_info:
        await clean_legacy_favorite_invalid_resources(
            folder_id=100,
            session_id="sid",
            get_session_func=missing_session,
            service_from_cookies=fake_service_from_cookies,
            service_cls=FakeBilibiliService,
        )

    assert exc_info.value.status_code == 401
