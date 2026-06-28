from types import SimpleNamespace

from langchain.schema import Document

from app.services.knowledge_base_presenters import (
    dedupe_ints,
    dedupe_strings,
    response_from_knowledge_base,
    search_result_from_document,
    source_from_document,
    supports_keyword_argument,
)


def test_response_from_knowledge_base_maps_public_fields():
    knowledge_base = SimpleNamespace(
        id=1,
        workspace_id=2,
        name="Main",
        description="Desc",
    )

    response = response_from_knowledge_base(knowledge_base)

    assert response.model_dump() == {
        "id": 1,
        "workspace_id": 2,
        "name": "Main",
        "description": "Desc",
    }


def test_search_result_from_document_maps_metadata():
    document = Document(
        page_content="content",
        metadata={
            "bvid": "BV1",
            "title": "Title",
            "url": "https://example.com",
        },
    )

    result = search_result_from_document(document)

    assert result.model_dump() == {
        "content": "content",
        "bvid": "BV1",
        "title": "Title",
        "url": "https://example.com",
    }


def test_source_from_document_uses_bvid_fallbacks():
    document = Document(page_content="content", metadata={"bvid": "BV1"})

    assert source_from_document(document) == {
        "type": "knowledge",
        "bvid": "BV1",
        "title": "BV1",
        "url": "https://www.bilibili.com/video/BV1",
    }


def test_dedupe_helpers_preserve_order_and_drop_empty_strings():
    assert dedupe_ints([1, 2, 1, 3]) == [1, 2, 3]
    assert dedupe_strings(["a", "", "a", "b", None]) == ["a", "b"]


def test_supports_keyword_argument_handles_kwargs_and_uninspectable_callables():
    class UninspectableCallable:
        @property
        def __signature__(self):
            raise ValueError("no signature")

        def __call__(self):
            return None

    def accepts_kwargs(**kwargs):
        return kwargs

    def explicit_keyword(*, provider=None):
        return provider

    assert supports_keyword_argument(accepts_kwargs, "provider")
    assert supports_keyword_argument(explicit_keyword, "provider")
    assert supports_keyword_argument(UninspectableCallable(), "provider")
