"""Compatibility adapter for non-streaming knowledge-base LLM answers."""

from collections.abc import Callable
from typing import Any


def build_complete_knowledge_base_answer(
    *,
    complete_llm_answer_resolver: Callable[[], Callable[..., tuple[str, str]]],
    prepare_web_search_tool_run: Callable[..., Any],
    status_from_web_search_state: Callable[..., dict | None],
    supports_keyword_argument: Callable[[Callable[..., Any], str], bool],
):
    async def complete_knowledge_base_answer(
        messages: list[dict],
        *,
        question: str,
        enable_web_search: bool,
        web_search_provider: str = "auto",
        tavily_api_key: str | None = None,
        llm_config: dict | None = None,
    ) -> tuple[str, str, list[dict[str, str]], dict | None]:
        def complete_llm_with_config(next_messages: list[dict]) -> tuple[str, str]:
            complete_llm_answer = complete_llm_answer_resolver()
            kwargs = {}
            if supports_keyword_argument(complete_llm_answer, "llm_config"):
                kwargs["llm_config"] = llm_config
            return complete_llm_answer(next_messages, **kwargs)

        if not enable_web_search:
            answer, thinking = complete_llm_with_config(messages)
            return answer, thinking, [], None

        tool_run, web_results, web_search_state = await prepare_web_search_tool_run(
            messages,
            question=question,
            provider=web_search_provider,
            tavily_api_key=tavily_api_key,
            llm_config=llm_config,
        )
        if tool_run.answer is not None:
            answer = tool_run.answer
            thinking = tool_run.thinking
        else:
            answer, thinking = complete_llm_with_config(tool_run.messages)

        return (
            answer,
            thinking,
            web_results,
            status_from_web_search_state(
                web_results,
                web_search_state,
            ),
        )

    return complete_knowledge_base_answer
