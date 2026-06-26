from collections.abc import Callable
from datetime import datetime
from typing import get_args, get_origin, get_type_hints

import pytest
from sqlalchemy import select

from app.models import FavoriteFolder, FavoriteVideo
from app.services.folder_ingestion import _delete_video_vectors_for_scope, sync_folder


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
