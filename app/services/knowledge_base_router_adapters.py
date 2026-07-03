"""Compatibility adapter assembly for knowledge-base router modules."""

from typing import Any

from app.services.knowledge_base_answer_adapter import (
    build_complete_knowledge_base_answer,
)
from app.services.knowledge_base_llm_runtime import (
    build_complete_llm_answer_adapter,
    build_prepare_llm_messages_with_tools_adapter,
    build_stream_llm_events_adapter,
    encode_web_search_progress,
)
from app.services.knowledge_base_web_search_compat import (
    build_web_search_orchestration_compat,
)


def build_knowledge_base_router_adapters(
    module: Any,
    *,
    answer_from_documents,
    build_knowledge_base_messages,
    stream_llm_events,
    complete_llm_answer,
    prepare_llm_messages_with_tools,
    encode_thinking_delta,
    status_from_web_search_state,
    supports_keyword_argument,
    source_from_document,
    format_web_search_context,
    enforce_markdown_output,
    apply_mode_instructions,
) -> dict[str, Any]:
    """Build legacy monkeypatch-compatible helpers for the router module."""

    def answer_from_documents_adapter(question, documents):
        return answer_from_documents(
            question,
            documents,
            source_from_document=source_from_document,
        )

    def build_messages_adapter(
        question,
        documents,
        web_results=None,
        *,
        enable_web_search=False,
        thinking_config=None,
    ):
        return build_knowledge_base_messages(
            question,
            documents,
            web_results,
            enable_web_search=enable_web_search,
            thinking_config=thinking_config,
            format_web_search_context=format_web_search_context,
            enforce_markdown_output=enforce_markdown_output,
            apply_mode_instructions=apply_mode_instructions,
            resolve_llm_config=getattr(module, "_resolve_llm_config"),
        )

    adapters = {
        "_encode_thinking_delta": encode_thinking_delta,
        "_encode_web_search_progress": encode_web_search_progress,
        "_stream_llm_events": build_stream_llm_events_adapter(
            stream_llm_events=stream_llm_events,
            resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
            get_llm_client=lambda config: getattr(module, "_get_llm_client")(config),
        ),
        "_complete_llm_answer": build_complete_llm_answer_adapter(
            complete_llm_answer=complete_llm_answer,
            resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
            get_llm_client=lambda config: getattr(module, "_get_llm_client")(config),
        ),
        "_prepare_llm_messages_with_tools": (
            build_prepare_llm_messages_with_tools_adapter(
                prepare_llm_messages_with_tools=prepare_llm_messages_with_tools,
                resolve_llm_config=lambda: getattr(module, "_resolve_llm_config")(),
                get_llm_client=lambda config: getattr(module, "_get_llm_client")(
                    config
                ),
            )
        ),
        "_answer_from_documents": answer_from_documents_adapter,
        "_build_knowledge_base_messages": build_messages_adapter,
    }
    adapters["_complete_knowledge_base_answer"] = build_complete_knowledge_base_answer(
        complete_llm_answer_resolver=lambda: getattr(module, "_complete_llm_answer"),
        prepare_web_search_tool_run=lambda *args, **kwargs: getattr(
            module,
            "_prepare_web_search_tool_run",
        )(*args, **kwargs),
        status_from_web_search_state=status_from_web_search_state,
        supports_keyword_argument=supports_keyword_argument,
    )
    adapters.update(build_web_search_orchestration_compat(module))
    return adapters
