from langchain.schema import Document

from app.services.rag_search import (
    legacy_similarity_search,
    scoped_similarity_search,
)


class FakeVectorStore:
    def __init__(self, documents=None):
        self.documents = documents or []
        self.calls = []

    def similarity_search(self, query, k, filter=None):
        self.calls.append({"query": query, "k": k, "filter": filter})
        return list(self.documents)


def test_legacy_similarity_search_returns_empty_for_blank_query():
    warnings = []
    vectorstore = FakeVectorStore()

    assert (
        legacy_similarity_search(
            "   ",
            vectorstore=vectorstore,
            warning_logger=lambda message: warnings.append(str(message)),
        )
        == []
    )

    assert vectorstore.calls == []
    assert warnings == ["检索查询为空"]


def test_legacy_similarity_search_filters_by_bvids_and_logs_recalled_documents():
    info_messages = []
    documents = [
        Document(
            page_content="line 1\nline 2",
            metadata={"bvid": "BV1", "title": "Title", "chunk_index": 3},
        )
    ]
    vectorstore = FakeVectorStore(documents)

    result = legacy_similarity_search(
        "question",
        vectorstore=vectorstore,
        k=2,
        bvids=["BV1", "BV2"],
        info_logger=lambda message: info_messages.append(str(message)),
    )

    assert result == documents
    assert vectorstore.calls == [
        {"query": "question", "k": 2, "filter": {"bvid": {"$in": ["BV1", "BV2"]}}}
    ]
    assert info_messages == [
        "检索完成：query='question'，召回=1",
        "召回[1] BV1 #3 Title | line 1 line 2",
    ]


def test_legacy_similarity_search_returns_empty_on_vectorstore_error():
    class BrokenVectorStore:
        def similarity_search(self, *_args, **_kwargs):
            raise RuntimeError("vector unavailable")

    warnings = []

    assert (
        legacy_similarity_search(
            "question",
            vectorstore=BrokenVectorStore(),
            warning_logger=lambda message: warnings.append(str(message)),
        )
        == []
    )
    assert warnings == ["向量检索失败: vector unavailable"]


def test_scoped_similarity_search_uses_workspace_knowledge_base_filter():
    vectorstore = FakeVectorStore([Document(page_content="content", metadata={})])

    result = scoped_similarity_search(
        "question",
        vectorstore=vectorstore,
        workspace_id=7,
        knowledge_base_id=11,
        k=4,
        bvids=["BV2", "BV1", "BV2"],
    )

    assert len(result) == 1
    assert vectorstore.calls == [
        {
            "query": "question",
            "k": 4,
            "filter": {
                "$and": [
                    {"workspace_id": 7},
                    {"knowledge_base_id": 11},
                    {"bvid": {"$in": ["BV1", "BV2"]}},
                ]
            },
        }
    ]


def test_scoped_similarity_search_returns_empty_for_blank_query():
    vectorstore = FakeVectorStore()

    assert (
        scoped_similarity_search(
            "",
            vectorstore=vectorstore,
            workspace_id=7,
            knowledge_base_id=11,
        )
        == []
    )
    assert vectorstore.calls == []
