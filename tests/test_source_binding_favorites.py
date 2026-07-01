from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.source_binding_favorites import (
    clean_invalid_bilibili_favorite_resources,
    execute_bilibili_favorite_moves,
    list_all_bilibili_favorite_videos,
    list_bilibili_favorite_folders,
    list_bilibili_favorite_videos,
    preview_bilibili_favorite_organization,
)


class FakeBilibiliFavoritesService:
    def __init__(self):
        self.closed = False
        self.moved = []

    async def get_user_info(self):
        return {"mid": 4242}

    async def get_user_favorites(self, mid):
        assert mid == 4242
        return [
            {"id": 10, "title": "默认收藏夹", "media_count": 3, "type": 1},
            {"id": 11, "title": "学习", "media_count": 2},
        ]

    async def get_favorite_content(self, media_id, pn, ps):
        assert (media_id, pn, ps) == (11, 2, 20)
        return {
            "info": {"id": 11, "title": "学习"},
            "has_more": True,
            "medias": [
                {
                    "bvid": "BV1",
                    "title": "Original",
                    "cover": "cover.jpg",
                    "duration": 99,
                    "upper": {"name": "Uploader"},
                    "cnt_info": {"play": 123},
                    "intro": "Intro",
                },
                {"bv_id": "BV2", "title": "Second"},
            ],
        }

    async def get_all_favorite_videos(self, media_id):
        assert media_id == 10
        return [
            {
                "bvid": "BVVALID",
                "title": "Valid",
                "cover": "valid.jpg",
                "duration": 10,
                "upper": {"name": "Uploader"},
                "intro": "Intro",
                "id": 501,
                "type": 2,
            },
            {"bvid": "BVLOST", "title": "已失效视频", "id": 502, "type": 2},
            {"bv_id": "BVDELETED", "title": "Gone", "attr": 9, "id": 503},
            {"title": "Missing bvid", "id": 504},
            {"bvid": "BVVALID", "title": "Duplicate", "id": 501, "type": 2},
        ]

    async def move_favorite_resources(self, src_media_id, tar_media_id, resources):
        self.moved.append(
            {
                "src_media_id": src_media_id,
                "tar_media_id": tar_media_id,
                "resources": list(resources),
            }
        )

    async def clean_favorite_resources(self, folder_id):
        return {"folder_id": folder_id, "removed": 2}

    async def close(self):
        self.closed = True


def _identity_display_title(video, overrides):
    bvid = video.get("bvid")
    return {
        **video,
        "display_title": overrides.get(bvid) or video.get("title"),
        "custom_title": overrides.get(bvid),
    }


def _context():
    return SimpleNamespace(id=7), SimpleNamespace(id=8), object()


@pytest.mark.asyncio
async def test_list_bilibili_favorite_folders_closes_service_and_marks_default():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()

    folders = await list_bilibili_favorite_folders(
        123,
        current_user,
        current_workspace,
        db,
        get_service=lambda *_args: fake_service,
    )

    assert [folder.media_id for folder in folders] == [10, 11]
    assert folders[0].is_default is True
    assert folders[1].is_default is False
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_list_bilibili_favorite_videos_adds_title_overrides_and_closes_service():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()
    override_calls = []

    async def get_overrides(_db, **kwargs):
        override_calls.append(kwargs)
        return {"BV1": "Custom"}

    result = await list_bilibili_favorite_videos(
        123,
        11,
        current_user,
        current_workspace,
        db,
        page=2,
        page_size=20,
        knowledge_base_id=456,
        get_service=lambda *_args: fake_service,
        get_video_title_overrides=get_overrides,
        with_display_title=_identity_display_title,
    )

    assert result["folder_info"] == {"id": 11, "title": "学习"}
    assert result["has_more"] is True
    assert result["videos"][0]["bvid"] == "BV1"
    assert result["videos"][0]["display_title"] == "Custom"
    assert result["videos"][1]["bvid"] == "BV2"
    assert override_calls == [
        {
            "workspace_id": 8,
            "knowledge_base_id": 456,
            "source_binding_id": 123,
            "bvids": ["BV1", "BV2"],
        }
    ]
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_list_all_bilibili_favorite_videos_filters_invalid_media():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()

    async def get_empty_overrides(*_args, **_kwargs):
        return {}

    result = await list_all_bilibili_favorite_videos(
        123,
        10,
        current_user,
        current_workspace,
        db,
        knowledge_base_id=456,
        get_service=lambda *_args: fake_service,
        get_video_title_overrides=get_empty_overrides,
        with_display_title=_identity_display_title,
    )

    assert result["total"] == 5
    assert result["valid"] == 2
    assert [video["bvid"] for video in result["videos"]] == ["BVVALID", "BVVALID"]
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_preview_bilibili_favorite_organization_dedupes_default_folder_items():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()

    result = await preview_bilibili_favorite_organization(
        123,
        999,
        current_user,
        current_workspace,
        db,
        get_service=lambda *_args: fake_service,
        warning_logger=lambda _message: None,
    )

    assert result["default_folder_id"] == 10
    assert result["folders"] == [
        {"media_id": 11, "title": "学习", "media_count": 2, "is_selected": True}
    ]
    assert result["stats"] == {"total": 5, "matched": 1}
    assert result["items"] == [
        {
            "bvid": "BVVALID",
            "title": "Valid",
            "resource_id": 501,
            "resource_type": 2,
            "target_folder_id": None,
            "target_folder_title": "默认收藏夹",
            "reason": "待手动分类",
        }
    ]
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_preview_bilibili_favorite_organization_rejects_missing_default_folder():
    current_user, current_workspace, db = _context()

    class NoDefaultFolderService(FakeBilibiliFavoritesService):
        async def get_user_favorites(self, mid):
            return [{"id": 11, "title": "学习"}]

    fake_service = NoDefaultFolderService()

    with pytest.raises(HTTPException) as exc_info:
        await preview_bilibili_favorite_organization(
            123,
            10,
            current_user,
            current_workspace,
            db,
            get_service=lambda *_args: fake_service,
        )

    assert exc_info.value.status_code == 400
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_execute_bilibili_favorite_moves_groups_resources_and_skips_noops():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()
    moves = [
        SimpleNamespace(resource_id=1, resource_type=2, target_folder_id=20),
        SimpleNamespace(resource_id=2, resource_type=2, target_folder_id=20),
        SimpleNamespace(resource_id=3, resource_type=2, target_folder_id=10),
    ]

    result = await execute_bilibili_favorite_moves(
        123,
        default_folder_id=10,
        moves=moves,
        current_user=current_user,
        current_workspace=current_workspace,
        db=db,
        get_service=lambda *_args: fake_service,
    )

    assert result == {"message": "移动完成", "moved": 2, "groups": 1}
    assert fake_service.moved == [
        {
            "src_media_id": 10,
            "tar_media_id": 20,
            "resources": ["1:2", "2:2"],
        }
    ]
    assert fake_service.closed is True


@pytest.mark.asyncio
async def test_clean_invalid_bilibili_favorite_resources_closes_service():
    current_user, current_workspace, db = _context()
    fake_service = FakeBilibiliFavoritesService()

    result = await clean_invalid_bilibili_favorite_resources(
        123,
        10,
        current_user,
        current_workspace,
        db,
        get_service=lambda *_args: fake_service,
    )

    assert result == {"ok": True, "data": {"folder_id": 10, "removed": 2}}
    assert fake_service.closed is True
