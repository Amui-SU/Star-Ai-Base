import pytest
from langchain.schema import Document

from app.services.rag_qa import (
    answer_rag_question,
    build_rag_answer_context_and_sources,
)


def test_build_rag_answer_context_and_sources_dedupes_sources():
    docs = [
        Document(
            page_content="  first chunk  ",
            metadata={"bvid": "BV1", "title": "First", "url": "https://custom/BV1"},
        ),
        Document(
            page_content=" ",
            metadata={"bvid": "BV2", "title": "Empty"},
        ),
        Document(
            page_content="second chunk",
            metadata={"bvid": "BV1", "title": "First duplicate"},
        ),
        Document(page_content="third chunk", metadata={"title": "Untitled"}),
    ]

    context, sources = build_rag_answer_context_and_sources(docs)

    assert context == (
        "【First】\nfirst chunk\n\n---\n\n"
        "【First duplicate】\nsecond chunk\n\n---\n\n"
        "【Untitled】\nthird chunk"
    )
    assert sources == [
        {"bvid": "BV1", "title": "First", "url": "https://custom/BV1"},
        {
            "bvid": "BV2",
            "title": "Empty",
            "url": "https://www.bilibili.com/video/BV2",
        },
    ]


@pytest.mark.asyncio
async def test_answer_rag_question_uses_fallback_when_collection_is_empty():
    fallback_calls = []

    async def fallback_answer(question, reason):
        fallback_calls.append((question, reason))
        return {"answer": "fallback", "sources": []}

    result = await answer_rag_question(
        "问题",
        k=5,
        bvids=None,
        get_collection_stats=lambda: {"total_chunks": 0},
        search_documents=lambda *_args, **_kwargs: pytest.fail("search not expected"),
        fallback_answer=fallback_answer,
        complete_answer=lambda *_args, **_kwargs: pytest.fail("LLM not expected"),
    )

    assert result == {"answer": "fallback", "sources": []}
    assert fallback_calls == [("问题", "知识库目前还没有内容")]


@pytest.mark.asyncio
async def test_answer_rag_question_searches_with_normalized_bvids_and_completes():
    search_calls = []
    complete_calls = []

    def search_documents(question, *, k, bvids):
        search_calls.append((question, k, bvids))
        return [
            Document(
                page_content="相关内容",
                metadata={"bvid": "BV1", "title": "Video"},
            )
        ]

    async def complete_answer(question, context):
        complete_calls.append((question, context))
        return "AI answer"

    result = await answer_rag_question(
        "问题",
        k=3,
        bvids=[],
        get_collection_stats=lambda: {"total_chunks": 8},
        search_documents=search_documents,
        fallback_answer=lambda *_args, **_kwargs: pytest.fail("fallback not expected"),
        complete_answer=complete_answer,
    )

    assert result == {
        "answer": "AI answer",
        "sources": [
            {
                "bvid": "BV1",
                "title": "Video",
                "url": "https://www.bilibili.com/video/BV1",
            }
        ],
    }
    assert search_calls == [("问题", 3, None)]
    assert complete_calls == [("问题", "【Video】\n相关内容")]


@pytest.mark.asyncio
async def test_answer_rag_question_handles_search_and_llm_failures():
    fallback_calls = []

    async def fallback_answer(question, reason):
        fallback_calls.append((question, reason))
        return {"answer": reason, "sources": []}

    result = await answer_rag_question(
        "检索失败问题",
        k=5,
        bvids=["BV1"],
        get_collection_stats=lambda: {"total_chunks": 2},
        search_documents=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("vector down")
        ),
        fallback_answer=fallback_answer,
        complete_answer=lambda *_args, **_kwargs: pytest.fail("LLM not expected"),
    )

    assert result == {"answer": "检索时遇到问题", "sources": []}
    assert fallback_calls == [("检索失败问题", "检索时遇到问题")]

    async def broken_complete_answer(_question, _context):
        raise RuntimeError("llm down")

    result = await answer_rag_question(
        "LLM失败问题",
        k=5,
        bvids=["BV1"],
        get_collection_stats=lambda: {"total_chunks": 2},
        search_documents=lambda *_args, **_kwargs: [
            Document(page_content="内容", metadata={"bvid": "BV1", "title": "Video"})
        ],
        fallback_answer=fallback_answer,
        complete_answer=broken_complete_answer,
    )

    assert result == {
        "answer": "AI 回答时发生错误: llm down",
        "sources": [
            {
                "bvid": "BV1",
                "title": "Video",
                "url": "https://www.bilibili.com/video/BV1",
            }
        ],
    }


@pytest.mark.asyncio
async def test_answer_rag_question_returns_sources_when_docs_have_no_text():
    result = await answer_rag_question(
        "问题",
        k=5,
        bvids=None,
        get_collection_stats=lambda: {"total_chunks": 2},
        search_documents=lambda *_args, **_kwargs: [
            Document(page_content=" ", metadata={"bvid": "BV1", "title": "Video"})
        ],
        fallback_answer=lambda *_args, **_kwargs: pytest.fail("fallback not expected"),
        complete_answer=lambda *_args, **_kwargs: pytest.fail("LLM not expected"),
    )

    assert result == {
        "answer": "检索到了相关视频，但没有找到有效的文本内容。可能是视频还未完成内容提取。",
        "sources": [
            {
                "bvid": "BV1",
                "title": "Video",
                "url": "https://www.bilibili.com/video/BV1",
            }
        ],
    }
