from langchain.schema import Document

from app.services.knowledge_base_messages import (
    answer_from_documents,
    build_knowledge_base_messages,
)


def _source_from_document(document):
    metadata = document.metadata or {}
    return {"title": metadata.get("title"), "bvid": metadata.get("bvid")}


def _format_web_search_context(results):
    return "\n".join(result["title"] for result in results)


def _enforce_markdown_output(messages):
    return [*messages, {"role": "system", "content": "markdown"}]


def _apply_mode_instructions(messages, thinking_enabled):
    return [
        *messages,
        {"role": "system", "content": f"thinking={thinking_enabled}"},
    ]


def test_answer_from_documents_returns_empty_response_without_documents():
    response = answer_from_documents(
        "问题",
        [],
        source_from_document=_source_from_document,
    )

    assert response.answer == "当前知识库中没有找到相关内容。"
    assert response.sources == []


def test_answer_from_documents_includes_context_and_sources():
    document = Document(
        page_content="资料正文",
        metadata={"title": "资料标题", "bvid": "BV1"},
    )

    response = answer_from_documents(
        "问题",
        [document],
        source_from_document=_source_from_document,
    )

    assert "关于“问题”可以参考" in response.answer
    assert "资料正文" in response.answer
    assert response.sources == [{"title": "资料标题", "bvid": "BV1"}]


def test_build_knowledge_base_messages_is_strict_without_web_search():
    document = Document(page_content="知识库正文", metadata={"title": "标题"})

    messages = build_knowledge_base_messages(
        "问题",
        [document],
        format_web_search_context=_format_web_search_context,
        enforce_markdown_output=_enforce_markdown_output,
        apply_mode_instructions=_apply_mode_instructions,
        resolve_llm_config=lambda: {"thinking_config": {}},
    )

    assert "请仅依据知识库资料回答" in messages[0]["content"]
    assert "【标题】\n知识库正文" in messages[1]["content"]
    assert messages[-1]["content"] == "thinking=False"


def test_build_knowledge_base_messages_allows_web_context_and_thinking_override():
    messages = build_knowledge_base_messages(
        "问题",
        [],
        [{"title": "外部网页"}],
        enable_web_search=True,
        thinking_config={"enabled": True},
        format_web_search_context=_format_web_search_context,
        enforce_markdown_output=_enforce_markdown_output,
        apply_mode_instructions=_apply_mode_instructions,
        resolve_llm_config=lambda: {"thinking_config": {}},
    )

    assert "优先依据知识库资料和联网搜索资料回答" in messages[0]["content"]
    assert "联网搜索资料：\n外部网页" in messages[1]["content"]
    assert messages[-1]["content"] == "thinking=True"
