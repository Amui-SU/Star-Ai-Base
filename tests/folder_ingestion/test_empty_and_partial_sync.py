from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import FavoriteFolder, FavoriteVideo, VideoCache
from app.schemas.content import ContentSource, VideoContent
from app.services.folder_ingestion import sync_folder


@pytest.mark.asyncio
async def test_sync_folder_skips_deletion_when_nonempty_folder_returns_empty_list(
    db_session_factory,
):
    class EmptyBilibili:
        async def get_favorite_content(self, folder_id, pn=1, ps=1):
            return {"info": {"title": "Folder A", "media_count": 3}}

        async def get_all_favorite_videos(self, folder_id):
            return []

    class UnusedContentFetcher:
        async def fetch_content(self, *_args, **_kwargs):
            raise AssertionError("empty folder guard should stop before fetching")

    class DeletingRag:
        def delete_video(self, bvid):
            raise AssertionError("empty folder guard should not delete vectors")

        def add_video_content(self, *_args, **_kwargs):
            raise AssertionError("empty folder guard should not add vectors")

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="session",
            media_id=10,
            title="Folder A",
            media_count=3,
            last_sync_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        session.add(FavoriteVideo(folder_id=folder.id, bvid="BVEXISTING"))
        await session.commit()

        result = await sync_folder(
            db=session,
            bili=EmptyBilibili(),
            rag=DeletingRag(),
            content_fetcher=UnusedContentFetcher(),
            session_id="session",
            folder_id=10,
        )

        rows = await session.execute(
            select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder.id)
        )

    assert result["removed"] == 0
    assert result["indexed"] == 1
    assert rows.scalars().all() == ["BVEXISTING"]


@pytest.mark.asyncio
async def test_partial_folder_sync_keeps_existing_unselected_videos(
    db_session_factory,
):
    class FakeBilibili:
        async def get_favorite_content(self, folder_id, pn=1, ps=1):
            return {"info": {"title": "Folder A", "media_count": 2}}

        async def get_all_favorite_videos(self, folder_id):
            return [
                {"bvid": "BV1ONLY", "title": "Video one", "attr": 0},
                {"bvid": "BV1SKIP", "title": "Video two", "attr": 0},
            ]

    class FakeContentFetcher:
        async def fetch_content(self, bvid, cid=None, title=None):
            return VideoContent(
                bvid=bvid,
                title=title or bvid,
                content="selected video content " * 5,
                source=ContentSource.BASIC_INFO,
            )

    class FakeRag:
        def delete_video(self, bvid):
            pass

        def add_video_content(self, *args, **kwargs):
            return 1

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="",
            media_id=10,
            title="Folder A",
            media_count=2,
            last_sync_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        session.add(FavoriteVideo(folder_id=folder.id, bvid="BV1OLD"))
        session.add(
            VideoCache(
                bvid="BV1OLD",
                title="Old video",
                content="old content " * 8,
                content_source=ContentSource.BASIC_INFO.value,
                is_processed=True,
            )
        )
        await session.commit()

        result = await sync_folder(
            db=session,
            bili=FakeBilibili(),
            rag=FakeRag(),
            content_fetcher=FakeContentFetcher(),
            session_id="",
            folder_id=10,
            include_bvids={"BV1ONLY"},
        )

        rows = await session.execute(
            select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder.id)
        )

    assert result["removed"] == 0
    assert set(rows.scalars().all()) == {"BV1OLD", "BV1ONLY"}
