from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_chat_router_delegates_message_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_messages.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    knowledge_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "build_overview_messages",
        "build_rag_messages",
        "build_fallback_messages",
        "build_direct_messages",
        "build_direct_messages_with_context",
        "build_db_list_messages",
        "build_db_summary_messages",
        "enforce_markdown_output",
        "apply_mode_instructions",
    }
    router_private_names = {
        "_build_overview_messages",
        "_build_rag_messages",
        "_build_fallback_messages",
        "_build_direct_messages",
        "_build_direct_messages_with_context",
        "_build_db_list_messages",
        "_build_db_summary_messages",
        "_enforce_markdown_output",
        "_apply_mode_instructions",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source
    assert "from app.services.chat_messages import" in knowledge_source
    assert "    _apply_mode_instructions," not in knowledge_source
    assert "    _enforce_markdown_output," not in knowledge_source
    assert declared_names.isdisjoint(router_private_names)


def test_chat_router_delegates_completion_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_completion.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "create_chat_completion_async",
        "is_llm_connection_error",
        "build_llm_unavailable_answer",
        "build_thinking_completion_options",
        "verify_provider_configuration",
        "encode_thinking_delta",
        "stream_llm_events",
        "complete_llm_answer",
        "complete_llm_answer_with_tools",
        "prepare_llm_messages_with_tools",
    }
    router_private_names = {
        "_create_chat_completion_async",
        "_is_llm_connection_error",
        "_build_llm_unavailable_answer",
        "_build_thinking_completion_options",
        "_verify_provider_configuration",
        "_encode_thinking_delta",
        "_stream_llm_events",
        "_complete_llm_answer",
        "_complete_llm_answer_with_tools",
        "_prepare_llm_messages_with_tools",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.chat_completion import" in chat_source
    assert declared_names.isdisjoint(router_private_names)


def test_chat_router_delegates_llm_client_factory_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/llm_client.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def get_llm_client" in service_source
    assert "from app.services.llm_client import" in chat_source
    assert "from openai import OpenAI" not in chat_source
    assert "OpenAI(" not in chat_source
    assert "_get_llm_client" not in declared_names
    assert (
        "get_llm_client as _get_llm_client" in chat_source
        or "_get_llm_client = get_llm_client" in chat_source
    )
