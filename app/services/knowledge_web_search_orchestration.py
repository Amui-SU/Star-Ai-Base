"""Runtime orchestration for knowledge-base web-search tool chains."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.knowledge_base_presenters import supports_keyword_argument
from app.services.knowledge_web_search import (
    FETCH_WEB_PAGE_TOOL,
    WEB_SEARCH_TOOL,
    append_web_search_context_message,
    append_web_search_no_results_message,
    build_web_search_queries,
    remove_web_search_no_results_messages,
    status_from_web_search_state,
)
from app.services.knowledge_web_search_tools import (
    FETCH_WEB_PAGE_CONTEXT_CHARS,
    FetchWebPage,
    MAX_FETCH_WEB_PAGE_CALLS,
    execute_fetch_web_page_tool,
    execute_web_search_tool,
)
from app.services.llm_tool_calls import LLMToolRunResult
from app.services.web_search import fetch_web_page as default_fetch_web_page
from app.services.web_search import search_web as default_search_web

WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS = 2.5
WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS = 60.0

SearchWeb = Callable[..., Awaitable[list[dict[str, str]]]]
PrepareMessagesWithTools = Callable[..., Awaitable[LLMToolRunResult]]
PrepareKnowledgeBaseWebSearch = Callable[..., Awaitable[tuple]]


async def run_initial_web_search(
    question: str,
    web_results: list[dict[str, str]],
    state: dict,
    *,
    search_web: SearchWeb = default_search_web,
) -> None:
    for query in build_web_search_queries(question):
        before_count = len(web_results)
        await execute_web_search_tool(
            {"query": query},
            web_results,
            state,
            search_web=search_web,
        )
        if len(web_results) > before_count:
            break


async def prepare_web_search_tool_run(
    messages: list[dict],
    *,
    question: str,
    prepare_llm_messages_with_tools: PrepareMessagesWithTools,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
    search_web: SearchWeb = default_search_web,
    fetch_web_page: FetchWebPage = default_fetch_web_page,
) -> tuple[LLMToolRunResult, list[dict[str, str]], dict]:
    web_results: list[dict[str, str]] = []
    web_search_state = {
        "attempted": False,
        "failed": False,
        "provider": provider,
        "tavily_api_key": tavily_api_key,
    }

    await run_initial_web_search(
        question,
        web_results,
        web_search_state,
        search_web=search_web,
    )
    initial_result_count = len(web_results)
    context_appended_result_count = initial_result_count
    if web_results:
        prepared_messages = append_web_search_context_message(messages, web_results)
    else:
        prepared_messages = append_web_search_no_results_message(
            messages,
            web_search_state,
        )

    def after_tool_messages(next_messages: list[dict]) -> list[dict]:
        nonlocal context_appended_result_count
        if len(web_results) <= context_appended_result_count:
            return next_messages

        cleaned_messages = remove_web_search_no_results_messages(next_messages)
        new_results = web_results[context_appended_result_count:]
        context_appended_result_count = len(web_results)
        return append_web_search_context_message(cleaned_messages, new_results)

    tool_run = await prepare_llm_messages_with_tools(
        prepared_messages,
        tools=[WEB_SEARCH_TOOL, FETCH_WEB_PAGE_TOOL],
        tool_handlers={
            "web_search": lambda arguments: execute_web_search_tool(
                arguments,
                web_results,
                web_search_state,
                search_web=search_web,
            ),
            "fetch_web_page": lambda arguments: execute_fetch_web_page_tool(
                arguments,
                web_results,
                web_search_state,
                fetch_web_page=fetch_web_page,
            ),
        },
        max_tool_calls=3,
        after_tool_messages=after_tool_messages,
        llm_config=llm_config,
    )

    if len(web_results) > context_appended_result_count:
        tool_run.messages = append_web_search_context_message(
            tool_run.messages,
            web_results[context_appended_result_count:],
        )

    return tool_run, web_results, web_search_state


async def prepare_knowledge_base_web_search(
    messages: list[dict],
    *,
    question: str,
    prepare_llm_messages_with_tools: PrepareMessagesWithTools,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
    search_web: SearchWeb = default_search_web,
    fetch_web_page: FetchWebPage = default_fetch_web_page,
) -> tuple[LLMToolRunResult, list[dict[str, str]], dict | None]:
    tool_run, web_results, web_search_state = await prepare_web_search_tool_run(
        messages,
        question=question,
        prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
        search_web=search_web,
        fetch_web_page=fetch_web_page,
    )

    return (
        tool_run,
        web_results,
        status_from_web_search_state(
            web_results,
            web_search_state,
        ),
    )


async def prepare_knowledge_base_web_search_with_heartbeats(
    messages: list[dict],
    *,
    question: str,
    prepare_knowledge_base_web_search: PrepareKnowledgeBaseWebSearch,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
    heartbeat_interval_seconds: float = WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS,
    tool_prep_timeout_seconds: float = WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS,
):
    prepare_kwargs: dict[str, Any] = {"question": question}
    if supports_keyword_argument(prepare_knowledge_base_web_search, "provider"):
        prepare_kwargs["provider"] = provider
    if supports_keyword_argument(
        prepare_knowledge_base_web_search,
        "tavily_api_key",
    ):
        prepare_kwargs["tavily_api_key"] = tavily_api_key
    if supports_keyword_argument(prepare_knowledge_base_web_search, "llm_config"):
        prepare_kwargs["llm_config"] = llm_config
    task = asyncio.create_task(
        prepare_knowledge_base_web_search(
            messages,
            **prepare_kwargs,
        )
    )
    heartbeat_count = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + tool_prep_timeout_seconds
    try:
        while not task.done():
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"web search tool chain timed out after "
                    f"{tool_prep_timeout_seconds:g}s"
                )
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=min(heartbeat_interval_seconds, remaining),
                )
                yield ("result", result)
                return
            except TimeoutError:
                if task.done():
                    yield ("result", task.result())
                    return
                if deadline - loop.time() <= 0:
                    raise TimeoutError(
                        f"web search tool chain timed out after "
                        f"{tool_prep_timeout_seconds:g}s"
                    )
                heartbeat_count += 1
                yield (
                    "heartbeat",
                    f"联网搜索仍在进行，正在整理外部资料（{heartbeat_count}）。",
                )
        yield ("result", task.result())
    except Exception:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        raise
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
