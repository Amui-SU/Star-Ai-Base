from collections.abc import Callable
from typing import get_args, get_origin, get_type_hints

import pytest

from app.models import VideoCache
from app.schemas.content import ContentSource
from app.services.folder_ingestion import _delete_video_vectors_for_scope, sync_folder
from app.services.folder_ingestion_content import (
    extract_video_info,
    is_better_source,
    should_refresh_cache,
    video_content_from_cache,
)
from app.services.folder_ingestion_records import get_video_cache_for_scope
from app.services.folder_ingestion_records import upsert_video_cache


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
    summary_cache = VideoCache(
        bvid="BVSUMMARY123",
        title="Summary Video",
        content="AI summary " * 12,
        content_source=ContentSource.AI_SUMMARY.value,
    )
    assert should_refresh_cache(summary_cache)

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
async def test_upsert_video_cache_persists_cid_for_later_timestamp_lookup(
    db_session_factory,
):
    async with db_session_factory() as session:
        await upsert_video_cache(
            session,
            "BVCIDHELPER",
            {
                "title": "CID Helper Video",
                "cid": 456,
                "intro": "用于测试时间戳生成",
            },
            workspace_id=7,
            knowledge_base_id=11,
        )
        await session.commit()

        cache = await get_video_cache_for_scope(
            session,
            "BVCIDHELPER",
            workspace_id=7,
            knowledge_base_id=11,
        )

    assert cache is not None
    assert cache.cid == 456
