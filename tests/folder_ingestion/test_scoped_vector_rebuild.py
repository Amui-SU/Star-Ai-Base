from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import FavoriteFolder, FavoriteVideo, VideoCache
from app.schemas.content import ContentSource
from app.services.folder_ingestion import sync_folder


@pytest.mark.asyncio
async def test_scoped_sync_rebuilds_missing_vectors_from_existing_cache(
    db_session_factory,
):
    class FakeBilibili:
        async def get_favorite_content(self, folder_id, pn=1, ps=1):
            return {"info": {"title": "Scoped Folder", "media_count": 1}}

        async def get_all_favorite_videos(self, folder_id):
            return [
                {
                    "bvid": "BV1CACHED",
                    "title": "Cached Video",
                    "attr": 0,
                    "cid": 123,
                }
            ]

    class FakeContentFetcher:
        async def fetch_content(self, *_args, **_kwargs):
            raise AssertionError("existing processed cache should be reused")

    class FakeRag:
        def __init__(self):
            self.deleted = []
            self.added = []

        def has_video_vectors_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            assert (workspace_id, knowledge_base_id, bvid) == (7, 11, "BV1CACHED")
            return False

        def delete_video_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            self.deleted.append((workspace_id, knowledge_base_id, bvid))

        def add_video_content(self, video, **kwargs):
            self.added.append((video, kwargs))
            return 1

    rag = FakeRag()

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="scoped-session",
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
            media_id=10,
            title="Scoped Folder",
            media_count=1,
            last_sync_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid="BV1CACHED",
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        session.add(
            VideoCache(
                bvid="BV1CACHED",
                title="Cached Video",
                content="cached transcript " * 8,
                content_source=ContentSource.SUBTITLE.value,
                is_processed=True,
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        await session.commit()

        result = await sync_folder(
            db=session,
            bili=FakeBilibili(),
            rag=rag,
            content_fetcher=FakeContentFetcher(),
            session_id="scoped-session",
            folder_id=10,
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
        )

    assert result["indexed"] == 1
    assert rag.deleted == [(7, 11, "BV1CACHED")]
    assert len(rag.added) == 1
    video, metadata = rag.added[0]
    assert video.bvid == "BV1CACHED"
    assert video.content.startswith("cached transcript")
    assert video.source == ContentSource.SUBTITLE
    assert metadata == {
        "workspace_id": 7,
        "knowledge_base_id": 11,
        "source_binding_id": 13,
    }


@pytest.mark.asyncio
async def test_scoped_sync_skips_reindex_when_old_vector_delete_fails(
    db_session_factory,
    monkeypatch,
):
    warnings = []
    monkeypatch.setattr(
        "app.services.folder_ingestion.logger.warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    class FakeBilibili:
        async def get_favorite_content(self, folder_id, pn=1, ps=1):
            return {"info": {"title": "Scoped Folder", "media_count": 1}}

        async def get_all_favorite_videos(self, folder_id):
            return [
                {
                    "bvid": "BV1LOCKED",
                    "title": "Locked Video",
                    "attr": 0,
                    "cid": 123,
                }
            ]

    class FakeContentFetcher:
        async def fetch_content(self, *_args, **_kwargs):
            raise AssertionError("existing processed cache should be reused")

    class FakeRag:
        def __init__(self):
            self.added = []

        def has_video_vectors_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            return False

        def delete_video_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            raise RuntimeError("vector store is locked")

        def add_video_content(self, video, **kwargs):
            self.added.append((video, kwargs))
            return 1

    rag = FakeRag()

    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id="scoped-session",
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
            media_id=10,
            title="Scoped Folder",
            media_count=1,
            last_sync_at=datetime(2026, 6, 14),
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid="BV1LOCKED",
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        session.add(
            VideoCache(
                bvid="BV1LOCKED",
                title="Locked Video",
                content="cached transcript " * 8,
                content_source=ContentSource.SUBTITLE.value,
                is_processed=True,
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        await session.commit()

        result = await sync_folder(
            db=session,
            bili=FakeBilibili(),
            rag=rag,
            content_fetcher=FakeContentFetcher(),
            session_id="scoped-session",
            folder_id=10,
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
        )

        rows = await session.execute(
            select(FavoriteVideo.bvid).where(FavoriteVideo.folder_id == folder.id)
        )

    assert result["indexed"] == 1
    assert rag.added == []
    assert rows.scalars().all() == ["BV1LOCKED"]
    assert any("删除旧向量失败" in message for message in warnings)
