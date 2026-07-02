import pytest
from sqlalchemy import select

from app.models import VideoCache
from app.schemas.content import ContentSource
from app.services.folder_ingestion_vector_runtime import (
    has_scoped_vectors,
    process_vector_target,
)


def test_has_scoped_vectors_uses_scope_checker_and_warning_callback():
    warnings = []

    class FakeRag:
        def __init__(self):
            self.checked = []

        def has_video_vectors_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            self.checked.append((workspace_id, knowledge_base_id, bvid))
            if bvid == "BVBAD":
                raise RuntimeError("vector store unavailable")
            return True

    rag = FakeRag()

    assert has_scoped_vectors(rag, "BVLEGACY") is True
    assert (
        has_scoped_vectors(
            rag,
            "BVGOOD",
            workspace_id=7,
            knowledge_base_id=11,
            warn=warnings.append,
        )
        is True
    )
    assert (
        has_scoped_vectors(
            rag,
            "BVBAD",
            workspace_id=7,
            knowledge_base_id=11,
            warn=warnings.append,
        )
        is False
    )

    assert rag.checked == [(7, 11, "BVGOOD"), (7, 11, "BVBAD")]
    assert warnings == ["检查 scoped 向量失败 [11/BVBAD]: vector store unavailable"]


@pytest.mark.asyncio
async def test_process_vector_target_reuses_cache_for_missing_scoped_vector(
    db_session_factory,
):
    class UnusedContentFetcher:
        async def fetch_content(self, *_args, **_kwargs):
            raise AssertionError("processed cache should be enough to rebuild vectors")

    class FakeRag:
        def __init__(self):
            self.deleted = []
            self.added = []

        def delete_video_in_knowledge_base(
            self, *, workspace_id, knowledge_base_id, bvid
        ):
            self.deleted.append((workspace_id, knowledge_base_id, bvid))

        def add_video_content(self, video, **kwargs):
            self.added.append((video, kwargs))
            return 2

    rag = FakeRag()
    warnings = []
    infos = []

    async with db_session_factory() as session:
        session.add(
            VideoCache(
                bvid="BVCACHED",
                title="Cached Video",
                content="cached transcript " * 8,
                content_source=ContentSource.SUBTITLE.value,
                is_processed=False,
                workspace_id=7,
                knowledge_base_id=11,
                source_binding_id=13,
            )
        )
        await session.commit()

        await process_vector_target(
            db=session,
            bvid="BVCACHED",
            meta={"title": "Cached Video", "cid": 123},
            rag=rag,
            content_fetcher=UnusedContentFetcher(),
            missing_vector_candidates={"BVCACHED"},
            workspace_id=7,
            knowledge_base_id=11,
            source_binding_id=13,
            warn=warnings.append,
            info=infos.append,
        )

        cache = (
            await session.execute(
                select(VideoCache).where(VideoCache.bvid == "BVCACHED")
            )
        ).scalar_one()

    assert cache.is_processed is True
    assert rag.deleted == [(7, 11, "BVCACHED")]
    assert len(rag.added) == 1
    video, metadata = rag.added[0]
    assert video.bvid == "BVCACHED"
    assert video.content.startswith("cached transcript")
    assert video.source == ContentSource.SUBTITLE
    assert metadata == {
        "workspace_id": 7,
        "knowledge_base_id": 11,
        "source_binding_id": 13,
    }
    assert warnings == []
    assert infos[-1] == "[BVCACHED] 向量化完成，块数=2"
