from datetime import datetime

import pytest

from app.models import (
    FavoriteFolder,
    FavoriteVideo,
    KnowledgeBaseChatRequest,
    KnowledgeBaseSearchRequest,
    VideoCache,
)


async def _add_folder(
    session,
    *,
    knowledge_base_id: int,
    media_id: int,
    title: str,
    synced: bool = True,
) -> FavoriteFolder:
    folder = FavoriteFolder(
        session_id=f"session-{knowledge_base_id}",
        knowledge_base_id=knowledge_base_id,
        media_id=media_id,
        title=title,
        last_sync_at=datetime(2026, 6, 13) if synced else None,
    )
    session.add(folder)
    await session.flush()
    return folder


async def _add_video(
    session,
    *,
    folder: FavoriteFolder,
    bvid: str,
    title: str,
    processed: bool = True,
    favorite_knowledge_base_id: int | None = None,
    cache_knowledge_base_id: int | None = None,
) -> None:
    session.add(
        FavoriteVideo(
            folder_id=folder.id,
            bvid=bvid,
            knowledge_base_id=(
                folder.knowledge_base_id
                if favorite_knowledge_base_id is None
                else favorite_knowledge_base_id
            ),
        )
    )
    session.add(
        VideoCache(
            bvid=bvid,
            title=title,
            knowledge_base_id=(
                folder.knowledge_base_id
                if cache_knowledge_base_id is None
                else cache_knowledge_base_id
            ),
            is_processed=processed,
        )
    )


def test_scope_request_fields_are_optional_and_backward_compatible():
    search = KnowledgeBaseSearchRequest(query="transformers")
    chat = KnowledgeBaseChatRequest(question="What is attention?")

    assert search.folder_ids is None
    assert search.bvids is None
    assert chat.folder_ids is None
    assert chat.bvids is None

    scoped_search = KnowledgeBaseSearchRequest(
        query="transformers",
        folder_ids=[20, 10],
        bvids=["BV2", "BV1"],
    )
    scoped_chat = KnowledgeBaseChatRequest(
        question="What is attention?",
        folder_ids=[10],
        bvids=["BV1"],
    )

    assert scoped_search.folder_ids == [20, 10]
    assert scoped_search.bvids == ["BV2", "BV1"]
    assert scoped_chat.folder_ids == [10]
    assert scoped_chat.bvids == ["BV1"]


@pytest.mark.asyncio
async def test_list_scope_options_only_returns_processed_videos_from_knowledge_base(
    db_session_factory,
):
    from app.models import KnowledgeScopeOptionsResponse
    from app.services.knowledge_scope import list_scope_options

    async with db_session_factory() as session:
        second = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=20,
            title="Second",
        )
        first = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="First",
        )
        empty = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=30,
            title="No processed videos",
        )
        unsynced = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=40,
            title="Unsynced",
            synced=False,
        )
        external = await _add_folder(
            session,
            knowledge_base_id=2,
            media_id=5,
            title="External",
        )

        await _add_video(
            session,
            folder=first,
            bvid="BV1B",
            title="Video B",
        )
        await _add_video(
            session,
            folder=first,
            bvid="BV1A",
            title="Video A",
        )
        await _add_video(
            session,
            folder=second,
            bvid="BV1UNPROCESSED",
            title="Not ready",
            processed=False,
        )
        await _add_video(
            session,
            folder=empty,
            bvid="BV1MISMATCH",
            title="Wrong favorite scope",
            favorite_knowledge_base_id=2,
        )
        await _add_video(
            session,
            folder=unsynced,
            bvid="BV1UNSYNCED",
            title="Unsynced video",
        )
        await _add_video(
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
async def test_resolve_scope_bvids_unions_folders_and_explicit_videos(
    db_session_factory,
):
    from app.services.knowledge_scope import resolve_scope_bvids

    async with db_session_factory() as session:
        folder = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Selected",
        )
        for bvid in ("BV1C", "BV1A"):
            await _add_video(
                session,
                folder=folder,
                bvid=bvid,
                title=bvid,
            )
        explicit_folder = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=20,
            title="Explicit source",
        )
        await _add_video(
            session,
            folder=explicit_folder,
            bvid="BV1B",
            title="Explicit",
        )
        await session.commit()

        result = await resolve_scope_bvids(
            session,
            knowledge_base_id=1,
            folder_media_ids=[10],
            requested_bvids=["BV1B", "BV1A", "BV1B"],
        )

    assert result == ["BV1A", "BV1B", "BV1C"]


@pytest.mark.asyncio
async def test_resolve_scope_bvids_rejects_external_video(db_session_factory):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        external = await _add_folder(
            session,
            knowledge_base_id=2,
            media_id=20,
            title="External",
        )
        await _add_video(
            session,
            folder=external,
            bvid="BV2EXTERNAL",
            title="External video",
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope, match="BV2EXTERNAL"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=None,
                requested_bvids=["BV2EXTERNAL"],
            )


@pytest.mark.asyncio
async def test_resolve_scope_bvids_requires_current_knowledge_base_favorite(
    db_session_factory,
):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        external = await _add_folder(
            session,
            knowledge_base_id=2,
            media_id=20,
            title="External",
        )
        session.add_all(
            [
                VideoCache(
                    bvid="BV1NOFAVORITE",
                    title="No favorite relation",
                    knowledge_base_id=1,
                    is_processed=True,
                ),
                FavoriteVideo(
                    folder_id=external.id,
                    bvid="BV1OTHERFAVORITE",
                    knowledge_base_id=2,
                ),
                VideoCache(
                    bvid="BV1OTHERFAVORITE",
                    title="Favorite belongs to another knowledge base",
                    knowledge_base_id=1,
                    is_processed=True,
                ),
            ]
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope) as exc_info:
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=None,
                requested_bvids=["BV1NOFAVORITE", "BV1OTHERFAVORITE"],
            )

    assert "BV1NOFAVORITE" in str(exc_info.value)
    assert "BV1OTHERFAVORITE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_scope_bvids_rejects_external_folder(db_session_factory):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        await _add_folder(
            session,
            knowledge_base_id=2,
            media_id=99,
            title="External",
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope, match="99"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=[99],
                requested_bvids=None,
            )


@pytest.mark.asyncio
async def test_resolve_scope_bvids_rejects_unprocessed_video(db_session_factory):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        folder = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Current",
        )
        await _add_video(
            session,
            folder=folder,
            bvid="BV1PENDING",
            title="Pending",
            processed=False,
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope, match="BV1PENDING"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=None,
                requested_bvids=["BV1PENDING"],
            )


@pytest.mark.asyncio
async def test_resolve_scope_bvids_rejects_unsynced_folder(db_session_factory):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Unsynced",
            synced=False,
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope, match="10"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=[10],
                requested_bvids=None,
            )


@pytest.mark.asyncio
async def test_resolve_scope_bvids_rejects_selection_without_retrievable_videos(
    db_session_factory,
):
    from app.services.knowledge_scope import InvalidKnowledgeScope, resolve_scope_bvids

    async with db_session_factory() as session:
        folder = await _add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Pending folder",
        )
        await _add_video(
            session,
            folder=folder,
            bvid="BV1PENDING",
            title="Pending",
            processed=False,
        )
        await session.commit()

        with pytest.raises(InvalidKnowledgeScope, match="10"):
            await resolve_scope_bvids(
                session,
                knowledge_base_id=1,
                folder_media_ids=[10],
                requested_bvids=None,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("folder_media_ids", "requested_bvids"),
    [
        (None, None),
        ([], []),
        (None, []),
        ([], None),
    ],
)
async def test_resolve_scope_bvids_returns_none_for_empty_selection(
    db_session_factory,
    folder_media_ids,
    requested_bvids,
):
    from app.services.knowledge_scope import resolve_scope_bvids

    async with db_session_factory() as session:
        result = await resolve_scope_bvids(
            session,
            knowledge_base_id=1,
            folder_media_ids=folder_media_ids,
            requested_bvids=requested_bvids,
        )

    assert result is None
