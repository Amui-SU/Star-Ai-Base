from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import declared_module_names
from tests.service_boundaries.helpers import get_project_root


def test_chat_router_does_not_keep_mutable_current_llm_provider():
    project_root = get_project_root()
    source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert "_current_llm_provider" not in source


def test_chat_router_delegates_configuration_boundaries_to_service():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_module_names(chat_source)
    service_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )

    assert (project_root / "app/services/chat_config.py").exists()
    assert "async def llm_config_response" in service_source
    assert "def current_user_llm_source" in service_source
    assert "from app.services.chat_config import" in chat_source
    assert "UserApiAccount.user_id == current_user.id" not in chat_source
    assert "account_by_provider" not in chat_source
    assert "providers.append(" not in chat_source
    assert declared_names.isdisjoint(
        {
            "PROVIDER_META",
            "PROVIDER_ENV_FIELDS",
            "SETTINGS_FIELD_BY_ENV",
            "PROVIDER_THINKING_SETTINGS_FIELDS",
            "PROVIDER_THINKING_TEMPLATES",
            "SUPPORTED_WEB_SEARCH_PROVIDERS",
            "SUPPORTED_TAVILY_SEARCH_DEPTHS",
            "_normalize_provider",
            "_current_default_llm_provider",
            "_resolve_llm_config",
            "_get_provider_thinking_template",
            "_parse_thinking_config",
            "_get_provider_thinking_config",
            "_env_file_path",
            "_read_env_values",
            "_write_env_values",
            "_normalize_web_search_provider",
            "_normalize_tavily_search_depth",
            "_web_search_config_response",
        }
    )


def test_chat_router_delegates_global_config_writes_to_service():
    project_root = get_project_root()
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    service_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )

    web_search_route_source = chat_source[
        chat_source.index("async def save_web_search_config(") : chat_source.index(
            "_llm_config_response = llm_config_response"
        )
    ]
    provider_config_route_source = chat_source[
        chat_source.index("async def save_llm_provider_config(") : chat_source.index(
            '@router.post("/llm/config")'
        )
    ]
    provider_switch_route_source = chat_source[
        chat_source.index("async def set_llm_config(") : chat_source.index(
            '@router.get("/health/llm")'
        )
    ]

    assert "def save_global_web_search_config" in service_source
    assert "def save_global_llm_provider_config" in service_source
    assert "def set_global_llm_provider" in service_source

    assert "save_global_web_search_config(" in web_search_route_source
    assert "_write_env_values(" not in web_search_route_source
    assert "settings.web_search_provider =" not in web_search_route_source
    assert "updates = {" not in web_search_route_source

    assert "save_global_llm_provider_config(" in provider_config_route_source
    assert "_write_env_values(" not in provider_config_route_source
    assert "_verify_provider_configuration(" not in provider_config_route_source
    assert "json.dumps(" not in provider_config_route_source
    assert "reset_rag_service()" not in provider_config_route_source

    assert "set_global_llm_provider(" in provider_switch_route_source
    assert "_write_env_values(" not in provider_switch_route_source


def test_chat_config_delegates_env_persistence_to_helper():
    project_root = get_project_root()
    chat_config_source = (project_root / "app/services/chat_config.py").read_text(
        encoding="utf-8"
    )
    env_helper_path = project_root / "app/services/chat_config_env.py"

    assert env_helper_path.exists()
    env_helper_source = env_helper_path.read_text(encoding="utf-8")
    assert "SETTINGS_FIELD_BY_ENV = {" in env_helper_source
    assert "def _env_file_path" in env_helper_source
    assert "def _read_env_values" in env_helper_source
    assert "def _write_env_values" in env_helper_source
    assert "def write_env_values_to_path" in env_helper_source

    assert "from app.services.chat_config_env import" in chat_config_source
    assert "SETTINGS_FIELD_BY_ENV = {" not in chat_config_source
    assert "def _env_file_path" not in chat_config_source
    assert "def _read_env_values" not in chat_config_source
    assert "def _write_env_values" not in chat_config_source


def test_chat_router_delegates_llm_tool_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/llm_tool_calls.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "LLMToolRunResult",
        "message_to_openai_dict",
        "append_no_more_tool_calls_instruction",
        "append_tool_call_results",
        "parse_tool_arguments",
        "extract_thinking_and_answer",
        "extract_dsml_text_tool_calls",
        "contains_dsml_tool_call_text",
    }
    router_private_names = {
        "_message_to_openai_dict",
        "_tool_call_to_dict",
        "_tool_call_id",
        "_tool_call_function",
        "_extract_dsml_text_tool_calls",
        "_contains_dsml_tool_call_text",
        "_append_no_more_tool_calls_instruction",
        "_normalize_tool_arguments",
        "_parse_tool_arguments",
        "_append_tool_call_results",
        "_extract_thinking_and_answer",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"class {name}" in service_source
    assert "from app.services.llm_tool_calls import" in chat_source
    assert declared_names.isdisjoint(router_private_names)


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
    assert "from app.services.chat_messages import" in chat_source
    assert "from app.services.chat_messages import" in knowledge_source
    assert "    _apply_mode_instructions," not in knowledge_source
    assert "    _enforce_markdown_output," not in knowledge_source
    assert declared_names.isdisjoint(router_private_names)


def test_chat_router_delegates_question_routing_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_routing.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "is_list_question",
        "is_summary_question",
        "is_general_question",
        "is_collection_intent",
        "is_overview_question",
        "route_with_rules",
        "route_with_llm",
        "extract_keywords",
        "filter_docs_by_keywords",
    }
    router_private_names = {
        "_is_list_question",
        "_is_summary_question",
        "_is_general_question",
        "_is_collection_intent",
        "_is_overview_question",
        "_route_with_rules",
        "_route_with_llm",
        "_extract_keywords",
        "_filter_docs_by_keywords",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source
    assert "from app.services.chat_routing import" in chat_source
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


def test_chat_router_delegates_video_context_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_video_context.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    declared_names = declared_callable_names(chat_source)

    expected_service_names = {
        "is_related_to_collection",
        "get_folder_ids_for_session",
        "get_bvids_by_folder_ids",
        "get_video_context",
        "get_video_titles_context",
    }
    router_private_names = {
        "_is_related_to_collection",
        "_get_folder_ids_for_session",
        "_get_bvids_by_folder_ids",
        "_get_video_context",
        "_get_video_titles_context",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.chat_video_context import" in chat_source
    assert "VideoCache.description.ilike" not in chat_source
    assert "FavoriteFolder.updated_at.desc()" not in chat_source
    assert "FavoriteVideo.folder_id == FavoriteFolder.id" not in chat_source
    assert declared_names.isdisjoint(router_private_names)


def test_chat_router_delegates_message_preparation_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_message_preparation.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def prepare_chat_messages" in service_source
    assert "from app.services.chat_message_preparation import" in chat_source
    assert "rag.search(question, k=5" not in chat_source
    assert "route, route_raw = _route_with_llm(" not in chat_source
    assert "context_parts, sources, seen_bvids = [], [], set()" not in chat_source


def test_chat_router_delegates_legacy_ask_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/chat_runtime.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    ask_route_source = chat_source[
        chat_source.index("async def ask_question(") : chat_source.index(
            '@router.post("/ask/stream")'
        )
    ]
    stream_route_source = chat_source[
        chat_source.index("async def ask_question_stream(") : chat_source.index(
            '@router.post("/search")'
        )
    ]

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def answer_legacy_chat" in service_source
    assert "async def stream_legacy_chat" in service_source
    assert "from app.services.chat_runtime import" in chat_source

    assert "answer_legacy_chat(" in ask_route_source
    assert "_resolve_llm_config(" not in ask_route_source
    assert "_prepare_messages(" not in ask_route_source
    assert "_get_llm_client(" not in ask_route_source
    assert "client.chat.completions.create(" not in ask_route_source
    assert "ChatResponse(" not in ask_route_source

    assert "stream_legacy_chat(" in stream_route_source
    assert "def generate" not in stream_route_source
    assert "_stream_llm_events(" not in stream_route_source
    assert "_encode_thinking_delta(" not in stream_route_source
    assert "json.dumps(" not in stream_route_source
