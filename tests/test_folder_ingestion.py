from collections.abc import Callable
from datetime import datetime
from typing import get_args, get_origin, get_type_hints

import pytest
from sqlalchemy import select

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    VideoCache,
)
from app.schemas.content import ContentSource, VideoContent
from app.services.folder_ingestion import _delete_video_vectors_for_scope, sync_folder
from app.services.folder_ingestion_content import (
    extract_video_info,
    is_better_source,
    should_refresh_cache,
    video_content_from_cache,
)
from app.services.folder_ingestion_records import get_video_cache_for_scope


def _unwrap_optional(annotation):
    return next(arg for arg in get_args(annotation) if arg is not type(None))


def test_sync_folder_progress_callback_annotation_matches_runtime_calls():
    callback_annotation = get_type_hints(sync_folder)["progress_callback"]
    callable_annotation = _unwrap_optional(callback_annotation)
    parameter_types, return_type = get_args(callable_annotation)

    assert get_origin(callable_annotation) is Callable
    assert parameter_types == [str, int, int]
    assert return_type is type(None)


def test_delete_video_vectors_for_scope_uses_matching_rag_delete_method():
    class FakeRag:
        def __init__(self):
            self.legacy_deleted = []
            self.scoped_deleted = []

        def delete_video(self, bvid):
            self.legacy_deleted.append(bvid)

        def delete_video_in_knowledge_base(self, **kwargs):
            self.scoped_deleted.append(kwargs)

    rag = FakeRag()

    _delete_video_vectors_for_scope(rag, "BVLEGACY")
    _delete_video_vectors_for_scope(
        rag,
        "BVSCOPED",
        workspace_id=7,
        knowledge_base_id=11,
    )

    assert rag.legacy_deleted == ["BVLEGACY"]
    assert rag.scoped_deleted == [
        {
            "workspace_id": 7,
            "knowledge_base_id": 11,
            "bvid": "BVSCOPED",
        }
    ]


def test_folder_ingestion_content_helpers_select_cache_and_source_policy():
    media = {
        "bvid": "BVHELPER123",
        "title": "Helper Video",
        "ugc": {"first_cid": 456},
    }
    cache = VideoCache(
        bvid="BVHELPER123",
        title="Helper Video",
        content="subtitle transcript " * 8,
        content_source=ContentSource.SUBTITLE.value,
        outline_json=[{"title": "Chapter"}],
    )

    assert extract_video_info(media) == ("BVHELPER123", "Helper Video", 456)
    assert is_better_source(ContentSource.ASR.value, ContentSource.SUBTITLE.value)
    assert not should_refresh_cache(cache)

    content = video_content_from_cache(cache, "BVHELPER123", "Helper Video")

    assert content is not None
    assert content.bvid == "BVHELPER123"
    assert content.source == ContentSource.SUBTITLE
    assert content.outline == [{"title": "Chapter"}]


@pytest.mark.asyncio
async def test_folder_ingestion_record_helpers_respect_scope(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(
            VideoCache(
                bvid="BVSCOPEHELPER",
                title="Wrong scope",
                workspace_id=1,
                knowledge_base_id=2,
                source_binding_id=None,
            )
        )
        session.add(
            VideoCache(
                bvid="BVSCOPEHELPER",
                title="Right scope",
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        await session.commit()

        cache = await get_video_cache_for_scope(
            session,
            "BVSCOPEHELPER",
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
        )

    assert cache is not None
    assert cache.title == "Right scope"


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
