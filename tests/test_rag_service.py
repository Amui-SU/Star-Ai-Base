from app.schemas.content import ContentSource, VideoContent
from app.services.rag_documents import build_video_content_text, build_video_documents
from app.services.rag_filters import (
    knowledge_base_filter,
    video_in_knowledge_base_filter,
)
from app.services.rag import RAGService


class FakeTextSplitter:
    def split_text(self, text: str):
        return [text]


class FakeVectorStore:
    def __init__(self):
        self.added_batches = []

    def add_documents(self, documents):
        self.added_batches.append(list(documents))


class SplittingTextSplitter:
    def split_text(self, text: str):
        return [text[:12], "   ", text[12:]]


def _service_with_vectorstore(vectorstore):
    service = RAGService.__new__(RAGService)
    service.collection_name = "test_collection"
    service.text_splitter = FakeTextSplitter()
    service.vectorstore = vectorstore
    return service


def test_add_video_content_writes_scoped_metadata_without_none_values():
    vectorstore = FakeVectorStore()
    service = _service_with_vectorstore(vectorstore)
    video = VideoContent(
        bvid="BV1RAGTEST",
        title="RAG Test",
        content="This transcript is long enough to be indexed.",
        source=ContentSource.ASR,
    )

    count = service.add_video_content(
        video,
        workspace_id=7,
        knowledge_base_id=11,
        source_binding_id=None,
    )

    assert count == 1
    document = vectorstore.added_batches[0][0]
    assert document.page_content == "This transcript is long enough to be indexed."
    assert document.metadata == {
        "workspace_id": 7,
        "knowledge_base_id": 11,
        "bvid": "BV1RAGTEST",
        "title": "RAG Test",
        "source": ContentSource.ASR.value,
        "chunk_index": 0,
        "url": "https://www.bilibili.com/video/BV1RAGTEST",
    }


def test_rag_document_helpers_build_content_and_metadata():
    video = VideoContent(
        bvid="BVHELPER",
        title="Helper Video",
        content="Transcript content long enough for vector storage.",
        source=ContentSource.SUBTITLE,
        outline=[
            {
                "title": "Chapter",
                "points": [
                    {"content": "Point A"},
                    {"content": ""},
                    {"content": "Point B"},
                ],
            }
        ],
    )

    text = build_video_content_text(video)
    documents = build_video_documents(
        video,
        text_splitter=SplittingTextSplitter(),
        workspace_id=9,
        knowledge_base_id=15,
        source_binding_id=22,
    )

    assert "Transcript content long enough" in text
    assert "## 内容提纲" in text
    assert "- Point A" in text
    assert "- Point B" in text
    assert [document.page_content for document in documents] == [
        "Transcript c",
        "ontent long enough for vector storage.\n\n\n## 内容提纲\n\n### Chapter\n- Point A\n- Point B",
    ]
    assert documents[0].metadata == {
        "workspace_id": 9,
        "knowledge_base_id": 15,
        "source_binding_id": 22,
        "bvid": "BVHELPER",
        "title": "Helper Video",
        "source": ContentSource.SUBTITLE.value,
        "chunk_index": 0,
        "url": "https://www.bilibili.com/video/BVHELPER",
    }


def test_add_video_content_skips_short_content_without_touching_vectorstore():
    vectorstore = FakeVectorStore()
    service = _service_with_vectorstore(vectorstore)
    video = VideoContent(
        bvid="BVSHORT",
        title="Short",
        content="too short",
        source=ContentSource.BASIC_INFO,
    )

    count = service.add_video_content(video, workspace_id=1, knowledge_base_id=2)

    assert count == 0
    assert vectorstore.added_batches == []


def test_rag_filter_helpers_build_scoped_filters():
    assert knowledge_base_filter(workspace_id=1, knowledge_base_id=2) == {
        "$and": [{"workspace_id": 1}, {"knowledge_base_id": 2}]
    }
    assert knowledge_base_filter(
        workspace_id=1,
        knowledge_base_id=2,
        bvids=["BV2", "BV1", "BV2"],
    ) == {
        "$and": [
            {"workspace_id": 1},
            {"knowledge_base_id": 2},
            {"bvid": {"$in": ["BV1", "BV2"]}},
        ]
    }
    assert video_in_knowledge_base_filter(
        workspace_id=1,
        knowledge_base_id=2,
        bvid="BV1",
    ) == {
        "$and": [
            {"workspace_id": 1},
            {"knowledge_base_id": 2},
            {"bvid": "BV1"},
        ]
    }


def test_has_video_vectors_in_knowledge_base_returns_false_on_collection_error():
    class BrokenCollection:
        def get(self, **kwargs):
            raise RuntimeError("vector store unavailable")

    service = _service_with_vectorstore(
        type("VectorStore", (), {"_collection": BrokenCollection()})()
    )

    assert (
        service.has_video_vectors_in_knowledge_base(
            workspace_id=1,
            knowledge_base_id=2,
            bvid="BVERR",
        )
        is False
    )


def test_delete_by_knowledge_base_uses_workspace_scope_and_reports_deleted_count():
    captured = {}

    class FakeCollection:
        def __init__(self):
            self.counts = [5, 2]

        def count(self):
            return self.counts.pop(0)

        def delete(self, where=None):
            captured["where"] = where

    service = _service_with_vectorstore(
        type("VectorStore", (), {"_collection": FakeCollection()})()
    )

    deleted = service.delete_by_knowledge_base(knowledge_base_id=22, workspace_id=9)

    assert deleted == 3
    assert captured["where"] == {
        "$and": [
            {"workspace_id": 9},
            {"knowledge_base_id": 22},
        ]
    }


def test_delete_video_in_knowledge_base_logs_readable_message(monkeypatch):
    messages = []

    class FakeCollection:
        def delete(self, where=None):
            pass

    service = _service_with_vectorstore(
        type("VectorStore", (), {"_collection": FakeCollection()})()
    )
    monkeypatch.setattr(
        "app.services.rag.logger.info",
        lambda message, *args, **kwargs: messages.append(str(message)),
    )

    service.delete_video_in_knowledge_base(
        workspace_id=3,
        knowledge_base_id=7,
        bvid="BVREADABLE",
    )

    assert messages == ["已删除知识库 7 内的视频 BVREADABLE"]
