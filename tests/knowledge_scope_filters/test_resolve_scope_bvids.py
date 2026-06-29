import pytest
from app.models import FavoriteVideo
from app.models import VideoCache
from app.services.knowledge_scope import InvalidKnowledgeScope
from app.services.knowledge_scope import resolve_scope_bvids

from tests.knowledge_scope_filters.helpers import add_folder
from tests.knowledge_scope_filters.helpers import add_video


@pytest.mark.asyncio
async def test_resolve_scope_bvids_unions_folders_and_explicit_videos(
    db_session_factory,
):

    async with db_session_factory() as session:
        folder = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Selected",
        )
        for bvid in ("BV1C", "BV1A"):
            await add_video(
                session,
                folder=folder,
                bvid=bvid,
                title=bvid,
            )
        explicit_folder = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=20,
            title="Explicit source",
        )
        await add_video(
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

    async with db_session_factory() as session:
        external = await add_folder(
            session,
            knowledge_base_id=2,
            media_id=20,
            title="External",
        )
        await add_video(
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

    async with db_session_factory() as session:
        external = await add_folder(
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

    async with db_session_factory() as session:
        await add_folder(
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

    async with db_session_factory() as session:
        await add_folder(
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

    async with db_session_factory() as session:
        folder = await add_folder(
            session,
            knowledge_base_id=1,
            media_id=10,
            title="Pending folder",
        )
        await add_video(
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

    async with db_session_factory() as session:
        result = await resolve_scope_bvids(
            session,
            knowledge_base_id=1,
            folder_media_ids=folder_media_ids,
            requested_bvids=requested_bvids,
        )

    assert result is None
