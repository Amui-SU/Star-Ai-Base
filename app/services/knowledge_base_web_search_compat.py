"""Compatibility shims for legacy knowledge-base web-search monkeypatch paths."""

from typing import Any

from app.services.knowledge_web_search import status_from_web_search_state
from app.services.knowledge_web_search_orchestration import (
    FETCH_WEB_PAGE_CONTEXT_CHARS,
    MAX_FETCH_WEB_PAGE_CALLS,
    WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS,
    WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS,
    execute_fetch_web_page_tool,
    execute_web_search_tool,
    prepare_knowledge_base_web_search_with_heartbeats,
    prepare_web_search_tool_run,
    run_initial_web_search,
)


async def legacy_execute_web_search_tool(
    module: Any,
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
) -> dict:
    return await execute_web_search_tool(
        arguments,
        web_results,
        state,
        search_web=getattr(module, "search_web"),
    )


async def legacy_execute_fetch_web_page_tool(
    module: Any,
    arguments: dict,
    web_results: list[dict[str, str]],
    state: dict,
) -> dict:
    return await execute_fetch_web_page_tool(
        arguments,
        web_results,
        state,
        fetch_web_page=getattr(module, "fetch_web_page"),
    )


async def legacy_run_initial_web_search(
    module: Any,
    question: str,
    web_results: list[dict[str, str]],
    state: dict,
) -> None:
    return await run_initial_web_search(
        question,
        web_results,
        state,
        search_web=getattr(module, "search_web"),
    )


async def legacy_prepare_web_search_tool_run(
    module: Any,
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
):
    return await prepare_web_search_tool_run(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
        prepare_llm_messages_with_tools=getattr(
            module,
            "_prepare_llm_messages_with_tools",
        ),
        search_web=getattr(module, "search_web"),
        fetch_web_page=getattr(module, "fetch_web_page"),
    )


async def legacy_prepare_knowledge_base_web_search(
    module: Any,
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
) -> tuple:
    tool_run, web_results, web_search_state = await getattr(
        module,
        "_prepare_web_search_tool_run",
    )(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
    )

    return (
        tool_run,
        web_results,
        status_from_web_search_state(
            web_results,
            web_search_state,
        ),
    )


def legacy_prepare_knowledge_base_web_search_with_heartbeats(
    module: Any,
    messages: list[dict],
    *,
    question: str,
    provider: str = "auto",
    tavily_api_key: str | None = None,
    llm_config: dict | None = None,
):
    return prepare_knowledge_base_web_search_with_heartbeats(
        messages,
        question=question,
        provider=provider,
        tavily_api_key=tavily_api_key,
        llm_config=llm_config,
        prepare_knowledge_base_web_search=getattr(
            module,
            "_prepare_knowledge_base_web_search",
        ),
        heartbeat_interval_seconds=getattr(
            module,
            "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        ),
        tool_prep_timeout_seconds=getattr(
            module,
            "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS",
        ),
    )


def build_web_search_orchestration_compat(module: Any) -> dict[str, Any]:
    return {
        "MAX_FETCH_WEB_PAGE_CALLS": MAX_FETCH_WEB_PAGE_CALLS,
        "FETCH_WEB_PAGE_CONTEXT_CHARS": FETCH_WEB_PAGE_CONTEXT_CHARS,
        "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS": WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS,
        "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS": WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS,
        "_execute_web_search_tool": (
            lambda arguments, web_results, state: legacy_execute_web_search_tool(
                module,
                arguments,
                web_results,
                state,
            )
        ),
        "_execute_fetch_web_page_tool": (
            lambda arguments, web_results, state: legacy_execute_fetch_web_page_tool(
                module,
                arguments,
                web_results,
                state,
            )
        ),
        "_run_initial_web_search": (
            lambda question, web_results, state: legacy_run_initial_web_search(
                module,
                question,
                web_results,
                state,
            )
        ),
        "_prepare_web_search_tool_run": (
            lambda messages, **kwargs: legacy_prepare_web_search_tool_run(
                module,
                messages,
                **kwargs,
            )
        ),
        "_prepare_knowledge_base_web_search": (
            lambda messages, **kwargs: legacy_prepare_knowledge_base_web_search(
                module,
                messages,
                **kwargs,
            )
        ),
        "_prepare_knowledge_base_web_search_with_heartbeats": (
            lambda messages, **kwargs: legacy_prepare_knowledge_base_web_search_with_heartbeats(
                module,
                messages,
                **kwargs,
            )
        ),
    }
