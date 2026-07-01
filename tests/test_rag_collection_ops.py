from app.services.rag_collection_ops import (
    collection_stats,
    delete_knowledge_base_vectors,
    delete_video_vectors_in_knowledge_base,
    has_video_vectors_in_knowledge_base,
)


def test_collection_stats_counts_unique_videos():
    class FakeCollection:
        def count(self):
            return 4

        def get(self, include=None):
            return {
                "metadatas": [
                    {"bvid": "BV1"},
                    {"bvid": "BV2"},
                    {"bvid": "BV1"},
                    {},
                    None,
                ]
            }

    assert collection_stats(FakeCollection(), collection_name="test") == {
        "total_chunks": 4,
        "total_videos": 2,
        "collection_name": "test",
    }


def test_collection_stats_returns_empty_payload_on_error():
    class BrokenCollection:
        def count(self):
            raise RuntimeError("unavailable")

    assert collection_stats(BrokenCollection(), collection_name="broken") == {
        "total_chunks": 0,
        "total_videos": 0,
        "collection_name": "broken",
    }


def test_delete_knowledge_base_vectors_uses_scope_and_reports_deleted_count():
    captured = {}

    class FakeCollection:
        def __init__(self):
            self.counts = [8, 3]

        def count(self):
            return self.counts.pop(0)

        def delete(self, where=None):
            captured["where"] = where

    deleted = delete_knowledge_base_vectors(
        FakeCollection(),
        knowledge_base_id=22,
        workspace_id=9,
    )

    assert deleted == 5
    assert captured["where"] == {
        "$and": [
            {"workspace_id": 9},
            {"knowledge_base_id": 22},
        ]
    }


def test_video_vector_helpers_use_scoped_filters():
    captured = {}

    class FakeCollection:
        def delete(self, where=None):
            captured["delete"] = where

        def get(self, where=None, limit=None):
            captured["get"] = {"where": where, "limit": limit}
            return {"ids": ["doc-1"]}

    collection = FakeCollection()

    delete_video_vectors_in_knowledge_base(
        collection,
        workspace_id=3,
        knowledge_base_id=7,
        bvid="BVHELPER",
    )
    exists = has_video_vectors_in_knowledge_base(
        collection,
        workspace_id=3,
        knowledge_base_id=7,
        bvid="BVHELPER",
    )

    expected_filter = {
        "$and": [
            {"workspace_id": 3},
            {"knowledge_base_id": 7},
            {"bvid": "BVHELPER"},
        ]
    }
    assert captured["delete"] == expected_filter
    assert captured["get"] == {"where": expected_filter, "limit": 1}
    assert exists is True
