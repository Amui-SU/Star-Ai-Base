"""Question answering orchestration helpers for RAGService."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from loguru import logger

from app.services.llm_errors import classify_upstream_error


FallbackAnswer = Callable[[str, str], Awaitable[dict[str, Any]]]
CompleteAnswer = Callable[[str, str], Awaitable[str]]
SearchDocuments = Callable[..., Sequence[Document]]


async def fallback_rag_answer(
    question: str,
    reason: str,
    *,
    fallback_prompt: ChatPromptTemplate,
    llm: Any,
) -> dict[str, Any]:
    """Use the fallback prompt when vector retrieval cannot answer."""
    try:
        chain = (
            {"question": RunnablePassthrough()}
            | fallback_prompt
            | llm
            | StrOutputParser()
        )

        answer = await chain.ainvoke(question)
        return {"answer": answer, "sources": []}
    except Exception as exc:
        failure = classify_upstream_error(exc)
        logger.error(failure.log_message("Fallback 回复失败"))
        return {
            "answer": f"抱歉，{reason}。您可以尝试构建更多收藏夹内容，或者换个问法试试。",
            "sources": [],
        }


def build_rag_answer_context_and_sources(
    docs: Sequence[Document],
) -> tuple[str, list[dict[str, str]]]:
    """Build answer context and deduplicated Bilibili sources from retrieved docs."""
    context_parts: list[str] = []
    seen_bvids: set[str] = set()
    sources: list[dict[str, str]] = []

    for doc in docs:
        metadata = doc.metadata or {}
        bvid = metadata.get("bvid", "")
        title = metadata.get("title", "未知标题")
        content = doc.page_content.strip()

        if content:
            context_parts.append(f"【{title}】\n{content}")

        if bvid and bvid not in seen_bvids:
            seen_bvids.add(bvid)
            sources.append(
                {
                    "bvid": bvid,
                    "title": title,
                    "url": metadata.get(
                        "url", f"https://www.bilibili.com/video/{bvid}"
                    ),
                }
            )

    return "\n\n---\n\n".join(context_parts), sources


async def complete_rag_answer(
    question: str,
    context: str,
    *,
    qa_prompt: ChatPromptTemplate,
    llm: Any,
) -> str:
    """Complete a RAG answer using the QA prompt and prepared context."""
    chain = (
        {"context": lambda _: context, "question": RunnablePassthrough()}
        | qa_prompt
        | llm
        | StrOutputParser()
    )

    return await chain.ainvoke(question)


async def answer_rag_question(
    question: str,
    *,
    k: int,
    bvids: Sequence[str] | None,
    get_collection_stats: Callable[[], dict[str, Any]],
    search_documents: SearchDocuments,
    fallback_answer: FallbackAnswer,
    complete_answer: CompleteAnswer,
) -> dict[str, Any]:
    """Answer one question using vector retrieval and LLM completion."""
    stats = get_collection_stats()
    if stats["total_chunks"] == 0:
        return await fallback_answer(question, "知识库目前还没有内容")

    try:
        docs = search_documents(question, k=k, bvids=bvids if bvids else None)
    except Exception as exc:
        logger.error(f"检索失败: {exc}")
        return await fallback_answer(question, "检索时遇到问题")

    if not docs:
        return await fallback_answer(question, "没有找到相关内容")

    context, sources = build_rag_answer_context_and_sources(docs)

    if not context:
        return {
            "answer": "检索到了相关视频，但没有找到有效的文本内容。可能是视频还未完成内容提取。",
            "sources": sources,
        }

    if not context.strip():
        return {"answer": "没有找到可用的内容来回答您的问题。", "sources": sources}

    try:
        answer = await complete_answer(question, context)
        return {"answer": answer, "sources": sources}
    except Exception as exc:
        failure = classify_upstream_error(exc)
        logger.error(failure.log_message("LLM 调用失败"))
        return {"answer": failure.message, "sources": sources}
