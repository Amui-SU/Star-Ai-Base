"""Summary chain helpers for RAGService."""

from collections.abc import Callable
from typing import Any

from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

ChainBuilder = Callable[[Any, Any], Any]


def build_summary_chain(summary_prompt: Any, llm: Any) -> Any:
    return {"content": RunnablePassthrough()} | summary_prompt | llm | StrOutputParser()


async def summarize_text_content(
    content: str,
    *,
    summary_prompt: Any,
    llm: Any,
    max_length: int = 10000,
    build_chain: ChainBuilder = build_summary_chain,
) -> str:
    if len(content) > max_length:
        content = content[:max_length] + "\n...(内容已截断)"

    chain = build_chain(summary_prompt, llm)
    return await chain.ainvoke(content)
