import pytest
from fastapi import HTTPException

from app.routers import favorites


class ClosingBilibiliService:
    instances = []

    def __init__(self):
        self.closed = False
        ClosingBilibiliService.instances.append(self)

    async def close(self):
        self.closed = True

    async def get_favorite_content(self, *args, **kwargs):
        raise RuntimeError("upstream failure")

    async def get_all_favorite_videos(self, *args, **kwargs):
        raise RuntimeError("upstream failure")

    async def get_user_favorites(self, *args, **kwargs):
        return [
            {
                "id": 100,
                "title": "默认收藏夹",
                "media_count": 1,
                "attr": 0,
            }
        ]

    async def move_favorite_resources(self, *args, **kwargs):
        raise RuntimeError("upstream failure")

    async def clean_favorite_resources(self, *args, **kwargs):
        raise RuntimeError("upstream failure")


@pytest.fixture(autouse=True)
def fake_bilibili_service(monkeypatch):
    ClosingBilibiliService.instances = []

    async def fake_get_session(session_id):
        return {
            "cookies": {
                "SESSDATA": "sess",
                "bili_jct": "csrf",
                "DedeUserID": "4242",
            },
            "user_info": {"mid": "4242"},
        }

    monkeypatch.setattr(favorites, "get_session", fake_get_session)
    monkeypatch.setattr(
        favorites,
        "bilibili_service_from_cookies",
        lambda cookies, service_cls: ClosingBilibiliService(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call_name", "args", "kwargs"),
    [
        ("get_favorite_videos", (100,), {"session_id": "sid"}),
        ("get_all_favorite_videos", (100,), {"session_id": "sid"}),
        (
            "organize_preview",
            (favorites.OrganizePreviewRequest(folder_id=100),),
            {"session_id": "sid"},
        ),
        (
            "organize_execute",
            (
                favorites.OrganizeExecuteRequest(
                    default_folder_id=100,
                    moves=[
                        favorites.OrganizeMoveItem(
                            resource_id=1,
                            resource_type=2,
                            target_folder_id=200,
                        )
                    ],
                ),
            ),
            {"session_id": "sid"},
        ),
        (
            "clean_invalid_resources",
            (favorites.CleanInvalidRequest(folder_id=100),),
            {"session_id": "sid"},
        ),
    ],
)
async def test_favorites_routes_close_bilibili_service_on_errors(
    call_name,
    args,
    kwargs,
):
    with pytest.raises(HTTPException):
        await getattr(favorites, call_name)(*args, **kwargs)

    assert ClosingBilibiliService.instances
    assert ClosingBilibiliService.instances[-1].closed is True
