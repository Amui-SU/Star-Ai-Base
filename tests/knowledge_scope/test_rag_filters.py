import pytest

from app.services.rag import RAGService


def test_scoped_rag_search_requires_workspace_and_knowledge_base_filter():
    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["query"] = query
            captured["k"] = k
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    result = service.search_in_knowledge_base(
        "人工智能",
        workspace_id=10,
        knowledge_base_id=20,
        k=3,
    )

    assert result == []
    assert captured["query"] == "人工智能"
    assert captured["k"] == 3
    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
        ]
    }


def test_scoped_rag_search_adds_normalized_bvid_filter():
    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    result = service.search_in_knowledge_base(
        "attention",
        workspace_id=10,
        knowledge_base_id=20,
        k=3,
        bvids=["BV1B", "BV1A", "BV1B"],
    )

    assert result == []
    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
            {"bvid": {"$in": ["BV1A", "BV1B"]}},
        ]
    }


@pytest.mark.parametrize("bvids", [None, []])
def test_scoped_rag_search_keeps_legacy_filter_for_empty_scope(bvids):
    captured = {}

    class FakeVectorStore:
        def similarity_search(self, query, k, filter=None):
            captured["filter"] = filter
            return []

    service = RAGService.__new__(RAGService)
    service.vectorstore = FakeVectorStore()

    service.search_in_knowledge_base(
        "attention",
        workspace_id=10,
        knowledge_base_id=20,
        bvids=bvids,
    )

    assert captured["filter"] == {
        "$and": [
            {"workspace_id": 10},
            {"knowledge_base_id": 20},
        ]
    }
