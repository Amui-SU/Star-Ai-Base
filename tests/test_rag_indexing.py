import pytest

from app.schemas.content import ContentSource, VideoContent
from app.services.rag_indexing import index_video_content, index_videos_batch


class FakeTextSplitter:
    def __init__(self, chunks):
        self.chunks = chunks

    def split_text(self, _text: str):
        return list(self.chunks)


class FakeVectorStore:
    def __init__(self):
        self.added_batches = []

    def add_documents(self, documents):
        self.added_batches.append(list(documents))


def _video(**overrides):
    values = {
        "bvid": "BVINDEX",
        "title": "Index Video",
        "content": "Transcript content long enough for vector storage.",
        "source": ContentSource.ASR,
    }
    values.update(overrides)
    return VideoContent(**values)


def test_index_video_content_writes_documents_in_batches_with_scope_metadata():
    vectorstore = FakeVectorStore()
    messages = []
    chunks = [f"chunk-{index}" for index in range(21)]

    count = index_video_content(
        _video(),
        vectorstore=vectorstore,
        text_splitter=FakeTextSplitter(chunks),
        workspace_id=7,
        knowledge_base_id=11,
        source_binding_id=13,
        info_logger=lambda message: messages.append(str(message)),
    )

    assert count == 21
    assert [len(batch) for batch in vectorstore.added_batches] == [10, 10, 1]
    first_document = vectorstore.added_batches[0][0]
    assert first_document.page_content == "chunk-0"
    assert first_document.metadata == {
        "workspace_id": 7,
        "knowledge_base_id": 11,
        "source_binding_id": 13,
        "bvid": "BVINDEX",
        "title": "Index Video",
        "source": ContentSource.ASR.value,
        "chunk_index": 0,
        "url": "https://www.bilibili.com/video/BVINDEX",
    }
    assert messages == ["[BVINDEX] 添加了 21 个文档块"]


def test_index_video_content_skips_short_content_before_vector_writes():
    vectorstore = FakeVectorStore()
    warnings = []

    count = index_video_content(
        _video(content="short"),
        vectorstore=vectorstore,
        text_splitter=FakeTextSplitter(["short"]),
        warning_logger=lambda message: warnings.append(str(message)),
    )

    assert count == 0
    assert vectorstore.added_batches == []
    assert warnings == ["[BVINDEX] 内容太少，跳过"]


def test_index_video_content_logs_and_reraises_vectorstore_errors():
    class BrokenVectorStore:
        def add_documents(self, _documents):
            raise RuntimeError("vector write failed")

    errors = []

    with pytest.raises(RuntimeError, match="vector write failed"):
        index_video_content(
            _video(),
            vectorstore=BrokenVectorStore(),
            text_splitter=FakeTextSplitter(["valid chunk"]),
            error_logger=lambda message: errors.append(str(message)),
        )

    assert errors == ["[BVINDEX] 添加到向量库失败: vector write failed"]


def test_index_videos_batch_counts_success_failure_chunks_and_progress():
    videos = [_video(bvid="BV1", title="First"), _video(bvid="BV2", title="Second")]
    progress_calls = []

    def add_video(video):
        if video.bvid == "BV2":
            raise RuntimeError("boom")
        return 3

    result = index_videos_batch(
        videos,
        add_video_content=add_video,
        progress_callback=lambda current, total, title: progress_calls.append(
            (current, total, title)
        ),
        error_logger=lambda _message: None,
    )

    assert result == {"success": 1, "failed": 1, "chunks": 3}
    assert progress_calls == [(1, 2, "First")]
