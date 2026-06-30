from datetime import datetime

import pytest
from app.models import FavoriteVideo
from app.models import VideoCache
from app.models import VideoTitleOverride
from app.schemas.knowledge_base import KnowledgeScopeOptionsResponse
from app.services.knowledge_scope import InvalidKnowledgeScope
from app.services.knowledge_scope import list_scope_options
from app.services.knowledge_scope import resolve_scope_bvids

from tests.knowledge_scope_filters.helpers import add_folder
from tests.knowledge_scope_filters.helpers import add_video


@pytest.mark.asyncio
async def test_list_scope_options_only_returns_processed_videos_from_knowledge_base(
    db_session_factory,
):

    async with db_session_factory() as session:
        second = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=20,
            title="Second",
        )
        first = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="First",
        )
        empty = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=30,
            title="No processed videos",
        )
        unsynced = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=40,
            title="Unsynced",
            synced=False,
        )
        external = await add_folder(
            session,
            knowledge_base_id=2,
            media_id=5,
            title="External",
        )

        await add_video(
            session,
            folder=first,
            bvid="BV1B",
            title="Video B",
        )
        await add_video(
            session,
            folder=first,
            bvid="BV1A",
            title="Video A",
        )
        await add_video(
            session,
            folder=second,
            bvid="BV1UNPROCESSED",
            title="Not ready",
            processed=False,
        )
        await add_video(
            session,
            folder=empty,
            bvid="BV1MISMATCH",
            title="Wrong favorite scope",
            favorite_knowledge_base_id=2,
        )
        await add_video(
            session,
            folder=unsynced,
            bvid="BV1UNSYNCED",
            title="Unsynced video",
        )
        await add_video(
            session,
            folder=external,
            bvid="BV2EXTERNAL",
            title="External video",
        )
        await session.commit()

        result = await list_scope_options(session, knowledge_base_id=1)

    assert isinstance(result, KnowledgeScopeOptionsResponse)
    assert [folder.media_id for folder in result.folders] == [10, 20, 30]
    assert result.folders[0].title == "First"
    assert result.folders[0].video_count == 2
    assert [(video.bvid, video.title) for video in result.folders[0].videos] == [
        ("BV1A", "Video A"),
        ("BV1B", "Video B"),
    ]
    assert result.folders[1].videos == []
    assert result.folders[1].video_count == 0
    assert result.folders[2].videos == []
    assert result.folders[2].video_count == 0


@pytest.mark.asyncio
async def test_scope_membership_excludes_mismatched_video_cache_scope(
    db_session_factory,
):

    async with db_session_factory() as session:
        folder = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Current",
        )
        await add_video(
            session,
            folder=folder,
            bvid="BV1SHARED",
            title="Shared cache",
            cache_knowledge_base_id=2,
        )
        await session.commit()

        options = await list_scope_options(session, knowledge_base_id=1)

        with pytest.raises(InvalidKnowledgeScope, match="10"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=[10],
                requested_bvids=None,
            )
        with pytest.raises(InvalidKnowledgeScope, match="BV1SHARED"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=None,
                requested_bvids=["BV1SHARED"],
            )

    assert options.folders[0].videos == []
    assert options.folders[0].video_count == 0


@pytest.mark.asyncio
async def test_list_scope_options_uses_custom_video_title(db_session_factory):

    async with db_session_factory() as session:
        folder = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Current",
            workspace_id=1,
        )
        await add_video(
            session,
            folder=folder,
            bvid="BV1CUSTOM",
            title="Original video",
            workspace_id=1,
        )
        session.add(
            VideoTitleOverride(
                workspace_id=1,
                knowledge_base_id=1,
                source_binding_id=None,
                bvid="BV1CUSTOM",
                custom_title="Custom video",
                created_by=1,
            )
        )
        await session.commit()

        options = await list_scope_options(session, knowledge_base_id=1)

    video = options.folders[0].videos[0]
    assert video.title == "Custom video"
    assert video.display_title == "Custom video"
    assert video.original_title == "Original video"
    assert video.custom_title == "Custom video"


@pytest.mark.asyncio
async def test_scope_uses_latest_synced_folder_for_each_media_id(
    db_session_factory,
):

    async with db_session_factory() as session:
        old = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Old",
            updated_at=datetime(2026, 6, 11),
        )
        superseded_tie = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Superseded tie",
            updated_at=datetime(2026, 6, 13),
        )
        latest = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Latest",
            updated_at=datetime(2026, 6, 13),
        )
        await add_video(
            session,
            folder=old,
            bvid="BV1OLD",
            title="Old video",
        )
        await add_video(
            session,
            folder=superseded_tie,
            bvid="BV1TIE",
            title="Superseded tie video",
        )
        await add_video(
            session,
            folder=latest,
            bvid="BV1LATEST",
            title="Latest video",
        )
        await session.commit()

        options = await list_scope_options(session, knowledge_base_id=1)
        folder_scope = await resolve_scope_bvids(
            session,
            knowledge_base_id=1,
            folder_media_ids=[10],
            requested_bvids=None,
        )
        with pytest.raises(InvalidKnowledgeScope) as exc_info:
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=None,
                requested_bvids=["BV1OLD", "BV1TIE"],
            )

    assert len(options.folders) == 1
    assert options.folders[0].media_id == 10
    assert options.folders[0].title == "Latest"
    assert [video.bvid for video in options.folders[0].videos] == ["BV1LATEST"]
    assert folder_scope == ["BV1LATEST"]
    assert "BV1OLD" in str(exc_info.value)
    assert "BV1TIE" in str(exc_info.value)
