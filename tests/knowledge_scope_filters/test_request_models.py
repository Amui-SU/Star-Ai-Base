from app.schemas.knowledge_base import KnowledgeBaseChatRequest
from app.schemas.knowledge_base import KnowledgeBaseSearchRequest


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
