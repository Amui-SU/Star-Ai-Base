import ast
from pathlib import Path


def test_router_package_exports_registered_routers():
    import app.routers as routers

    project_root = Path(__file__).resolve().parents[1]
    main_source = (project_root / "app/main.py").read_text(encoding="utf-8")
    expected = {
        line.strip().removeprefix("app.include_router(").removesuffix(".router)")
        for line in main_source.splitlines()
        if line.strip().startswith("app.include_router(")
    }

    assert set(routers.__all__) == expected
    for router_name in expected:
        assert hasattr(routers, router_name)
        assert hasattr(getattr(routers, router_name), "router")


def test_primary_routers_do_not_import_legacy_knowledge_router():
    project_root = Path(__file__).resolve().parents[1]

    for relative_path in [
        "app/routers/knowledge_bases.py",
        "app/routers/imports.py",
        "app/routers/chat.py",
    ]:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "app.routers.knowledge import" not in source


def test_chat_router_does_not_keep_mutable_current_llm_provider():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")

    assert "_current_llm_provider" not in source


def test_chat_router_delegates_configuration_boundaries_to_service():
    project_root = Path(__file__).resolve().parents[1]
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    chat_module = ast.parse(chat_source)

    declared_names = set()
    for node in chat_module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            declared_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declared_names.add(target.id)

    assert (project_root / "app/services/chat_config.py").exists()
    assert "from app.services.chat_config import" in chat_source
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


def test_chat_router_delegates_llm_tool_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/llm_tool_calls.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    chat_module = ast.parse(chat_source)

    declared_names = {
        node.name
        for node in chat_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

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


def test_web_search_service_delegates_fetch_and_safety_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/web_search.py"
    safety_path = project_root / "app/services/web_search_safety.py"
    fetcher_path = project_root / "app/services/web_page_fetcher.py"
    parsers_path = project_root / "app/services/web_search_parsers.py"
    source = service_path.read_text(encoding="utf-8")
    module = ast.parse(source)

    declared_names = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    assert safety_path.exists()
    assert fetcher_path.exists()
    assert parsers_path.exists()
    assert "from app.services.web_search_safety import" in source
    assert "from app.services.web_page_fetcher import" in source
    assert "from app.services.web_search_parsers import" in source
    assert len(source.splitlines()) <= 560
    assert declared_names.isdisjoint(
        {
            "_DuckDuckGoResultParser",
            "_SogouResultParser",
            "_YahooResultParser",
            "_ReadableHTMLParser",
            "_is_supported_content_type",
            "_charset_from_content_type",
            "_decode_body",
        }
    )


def test_chat_router_delegates_message_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/chat_messages.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    knowledge_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    chat_module = ast.parse(chat_source)

    declared_names = {
        node.name
        for node in chat_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

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
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/chat_routing.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    chat_module = ast.parse(chat_source)

    declared_names = {
        node.name
        for node in chat_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

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
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/chat_completion.py"
    chat_source = (project_root / "app/routers/chat.py").read_text(encoding="utf-8")
    chat_module = ast.parse(chat_source)

    declared_names = {
        node.name
        for node in chat_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

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


def test_knowledge_base_router_delegates_web_search_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/knowledge_web_search.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    router_module = ast.parse(router_source)

    declared_names = set()
    for node in router_module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            declared_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declared_names.add(target.id)

    expected_service_names = {
        "MAX_WEB_CONTEXT_RESULTS",
        "MAX_INITIAL_WEB_SEARCH_QUERIES",
        "MAX_WEB_SEARCH_QUERY_CHARS",
        "WEB_SEARCH_TOOL",
        "FETCH_WEB_PAGE_TOOL",
        "format_web_search_context",
        "build_web_search_queries",
        "source_from_web_result",
        "append_web_result",
        "web_search_failed_status_from_exception",
        "status_from_web_search_state",
        "append_web_search_context_message",
        "append_web_search_no_results_message",
        "remove_web_search_no_results_messages",
    }
    router_private_names = {
        "MAX_WEB_CONTEXT_RESULTS",
        "MAX_INITIAL_WEB_SEARCH_QUERIES",
        "MAX_WEB_SEARCH_QUERY_CHARS",
        "WEB_SEARCH_TOOL",
        "FETCH_WEB_PAGE_TOOL",
        "_format_web_search_context",
        "_normalize_web_search_query",
        "_compact_web_search_query",
        "_append_unique_query",
        "_build_web_search_queries",
        "_source_from_web_result",
        "_append_web_result",
        "_web_search_status",
        "_exception_summary",
        "_web_search_failed_status_from_exception",
        "_web_search_result_details",
        "_web_search_diagnostic_message",
        "_append_web_search_diagnostics",
        "_status_from_web_search_state",
        "_append_web_search_context_message",
        "_append_web_search_no_results_message",
        "_is_web_search_no_results_message",
        "_remove_web_search_no_results_messages",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name} =" in service_source
    assert "from app.services.knowledge_web_search import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_knowledge_base_router_delegates_web_search_orchestration_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/knowledge_web_search_orchestration.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    router_module = ast.parse(router_source)

    declared_names = set()
    for node in router_module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            declared_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declared_names.add(target.id)

    expected_service_names = {
        "MAX_FETCH_WEB_PAGE_CALLS",
        "FETCH_WEB_PAGE_CONTEXT_CHARS",
        "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS",
        "execute_web_search_tool",
        "execute_fetch_web_page_tool",
        "run_initial_web_search",
        "prepare_web_search_tool_run",
        "prepare_knowledge_base_web_search",
        "prepare_knowledge_base_web_search_with_heartbeats",
    }
    router_private_names = {
        "MAX_FETCH_WEB_PAGE_CALLS",
        "FETCH_WEB_PAGE_CONTEXT_CHARS",
        "WEB_SEARCH_HEARTBEAT_INTERVAL_SECONDS",
        "WEB_SEARCH_TOOL_PREP_TIMEOUT_SECONDS",
        "_execute_web_search_tool",
        "_execute_fetch_web_page_tool",
        "_run_initial_web_search",
        "_prepare_web_search_tool_run",
        "_prepare_knowledge_base_web_search",
        "_prepare_knowledge_base_web_search_with_heartbeats",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name} =" in service_source
    assert (
        "from app.services.knowledge_web_search_orchestration import" in router_source
    )
    assert declared_names.isdisjoint(router_private_names)


def test_knowledge_base_router_delegates_presenter_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/knowledge_base_presenters.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    router_module = ast.parse(router_source)

    declared_names = {
        node.name
        for node in router_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    expected_service_names = {
        "supports_keyword_argument",
        "response_from_knowledge_base",
        "search_result_from_document",
        "source_from_document",
        "dedupe_ints",
        "dedupe_strings",
        "nullable_equal",
    }
    router_private_names = {
        "_supports_keyword_argument",
        "_response",
        "_search_result",
        "_source_from_document",
        "_dedupe_ints",
        "_dedupe_strings",
        "_nullable_equal",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source
    assert "from app.services.knowledge_base_presenters import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_knowledge_base_router_delegates_message_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/knowledge_base_messages.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    router_module = ast.parse(router_source)

    declared_names = {
        node.name
        for node in router_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    expected_service_names = {
        "answer_from_documents",
        "build_knowledge_base_messages",
    }
    router_private_names = {
        "_answer_from_documents",
        "_build_knowledge_base_messages",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source
    assert "from app.services.knowledge_base_messages import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_favorite_router_uses_shared_default_folder_detection():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/favorites.py").read_text(encoding="utf-8")

    assert "def _is_default_folder" not in source
    assert "is_legacy_default_favorite_folder" in source


def test_system_auth_router_uses_logger_for_tracebacks():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/routers/system_auth.py").read_text(encoding="utf-8")

    assert "traceback.print_exc" not in source
    assert "import traceback" not in source


def test_system_auth_router_delegates_oauth_state_helpers_to_service():
    project_root = Path(__file__).resolve().parents[1]
    service_path = project_root / "app/services/system_auth_oauth.py"
    router_source = (project_root / "app/routers/system_auth.py").read_text(
        encoding="utf-8"
    )
    router_module = ast.parse(router_source)

    declared_names = {
        node.name
        for node in router_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    expected_service_names = {
        "OAUTH_STATE_COOKIE_NAME",
        "frontend_origin_is_allowed",
        "normalize_frontend_origin",
        "frontend_url_from_request",
        "frontend_url_from_state",
        "oauth_signing_key",
        "make_oauth_state",
        "decode_oauth_state",
        "verify_oauth_state",
        "new_oauth_state_nonce",
        "set_oauth_state_cookie",
        "clear_oauth_state_cookie",
        "oauth_state_nonce_is_valid",
        "oauth_user_email",
    }
    router_private_names = {
        "_frontend_origin_is_allowed",
        "_normalize_frontend_origin",
        "_frontend_url_from_request",
        "_frontend_url_from_state",
        "_oauth_signing_key",
        "_make_oauth_state",
        "_decode_oauth_state",
        "_verify_oauth_state",
        "_new_oauth_state_nonce",
        "_set_oauth_state_cookie",
        "_clear_oauth_state_cookie",
        "_oauth_state_nonce_is_valid",
        "_oauth_user_email",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"{name} =" in service_source
    assert "from app.services.system_auth_oauth import" in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_database_legacy_migration_entrypoint_has_no_nested_helpers():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app/database.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    target = next(
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_ensure_sqlite_legacy_columns"
    )

    nested_helpers = [
        node.name
        for node in ast.walk(target)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node is not target
    ]

    assert nested_helpers == []


def test_ingestion_task_persistence_and_status_mapping_live_in_service():
    project_root = Path(__file__).resolve().parents[1]
    service_source = (project_root / "app/services/ingestion_tasks.py").read_text(
        encoding="utf-8"
    )
    imports_source = (project_root / "app/routers/imports.py").read_text(
        encoding="utf-8"
    )
    knowledge_bases_source = (
        project_root / "app/routers/knowledge_bases.py"
    ).read_text(encoding="utf-8")

    assert "def build_status_payload" in service_source
    assert "async def create_ingestion_task" in service_source
    assert "async def update_ingestion_task" in service_source
    assert "from app.services.ingestion_tasks import" in imports_source
    assert "from app.services.ingestion_tasks import" in knowledge_bases_source
    assert "async def _create_import_task" not in imports_source
    assert "async def _update_import_task" not in imports_source
    assert "async def _update_task" not in knowledge_bases_source
    assert "update_ingestion_task(" in imports_source
    assert "update_ingestion_task(" in knowledge_bases_source
    assert "return build_status_payload(task)" in knowledge_bases_source
    assert '"processed_videos": task.processed_items' not in knowledge_bases_source


def test_scoped_folder_sync_tests_do_not_import_legacy_router():
    project_root = Path(__file__).resolve().parents[1]

    for relative_path in [
        "tests/test_knowledge_base_scoping.py",
        "tests/test_folder_ingestion.py",
    ]:
        test_file = project_root / relative_path
        if not test_file.exists():
            continue
        source = test_file.read_text(encoding="utf-8")
        assert "from app.routers.knowledge import _sync_folder" not in source


def test_knowledge_base_web_search_helper_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    web_search_test = project_root / "tests" / "test_knowledge_base_web_search.py"

    assert web_search_test.exists()
    web_search_source = web_search_test.read_text(encoding="utf-8")
    for test_name in [
        "test_web_search_context_is_marked_as_sandboxed_but_usable",
        "test_knowledge_base_prompt_is_strict_when_web_search_disabled",
        "test_knowledge_base_prompt_allows_general_knowledge_when_context_is_empty",
        "test_web_search_query_generation_adds_compact_query",
        "test_web_search_context_limits_results_used",
        "test_fetch_web_page_tool_limits_fetch_calls",
    ]:
        assert test_name not in scoping_source
        assert test_name in web_search_source


def test_knowledge_base_web_search_stream_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    streaming_test = (
        project_root / "tests" / "test_knowledge_base_web_search_streaming.py"
    )
    streaming_dir = project_root / "tests" / "knowledge_base_web_search_streaming"
    streaming_files = [
        streaming_dir / "test_stream_status.py",
        streaming_dir / "test_stream_heartbeats.py",
        streaming_dir / "test_stream_sources.py",
    ]

    assert streaming_test.exists()
    for streaming_file in streaming_files:
        assert streaming_file.exists()
    streaming_source = "\n".join(
        streaming_file.read_text(encoding="utf-8") for streaming_file in streaming_files
    )
    for test_name in [
        "test_scoped_chat_stream_reports_web_search_no_results",
        "test_scoped_chat_stream_reports_socks_dependency_failure",
        "test_scoped_chat_stream_emits_web_search_progress_before_tool_setup",
        "test_scoped_chat_stream_emits_web_search_heartbeat_while_preparing",
        "test_web_search_heartbeat_generator_cancels_prepare_task_on_close",
        "test_web_search_heartbeat_generator_times_out_tool_setup",
        "test_web_search_tool_prep_timeout_allows_slow_model_tool_planning",
        "test_scoped_chat_stream_adds_web_sources_from_initial_search",
        "test_scoped_chat_stream_uses_final_stream_after_tool_decision",
    ]:
        assert test_name not in scoping_source
        assert test_name in streaming_source


def test_knowledge_base_web_search_api_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    api_test = project_root / "tests" / "test_knowledge_base_web_search_api.py"
    api_dir = project_root / "tests" / "knowledge_base_web_search_api"

    assert api_test.exists()
    api_source = api_test.read_text(encoding="utf-8")
    assert (
        "test_knowledge_base_web_search_api_tests_delegate_to_focused_files"
        in api_source
    )
    assert len(api_source.splitlines()) <= 80
    focused_source = "\n".join(
        (api_dir / relative_path).read_text(encoding="utf-8")
        for relative_path in [
            "test_tool_chain.py",
            "test_fetch_page.py",
            "test_toggle_fallback.py",
        ]
    )
    for test_name in [
        "test_scoped_chat_lets_llm_call_web_search_tool_when_enabled",
        "test_scoped_chat_reports_socks_dependency_failure",
        "test_scoped_chat_web_search_tool_chain_executes_model_requested_query",
        "test_scoped_chat_web_search_tool_accepts_query_alias_arguments",
        "test_scoped_chat_tool_chain_can_fetch_selected_web_page",
        "test_scoped_chat_direct_fetch_tool_reports_page_source",
        "test_scoped_chat_does_not_web_search_by_default",
        "test_scoped_chat_forces_web_search_when_enabled_without_model_tool_call",
    ]:
        assert test_name not in scoping_source
        assert test_name in focused_source


def test_knowledge_base_web_search_tool_run_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    tool_run_test = (
        project_root / "tests" / "test_knowledge_base_web_search_tool_run.py"
    )

    assert tool_run_test.exists()
    tool_run_source = tool_run_test.read_text(encoding="utf-8")
    for test_name in [
        "test_initial_web_context_is_not_duplicated_after_tool_run",
        "test_initial_web_search_no_results_is_visible_to_model",
        "test_web_search_tool_run_uses_request_provider",
        "test_web_search_tool_run_uses_tavily_api_key",
        "test_initial_web_search_diagnostics_are_reported_when_search_fails",
        "test_only_new_tool_results_are_appended_after_initial_web_context",
        "test_tool_web_results_remove_initial_no_results_instruction",
    ]:
        assert test_name not in scoping_source
        assert test_name in tool_run_source


def test_knowledge_base_web_search_fallback_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    fallback_test = (
        project_root / "tests" / "test_knowledge_base_web_search_fallback.py"
    )

    assert fallback_test.exists()
    fallback_source = fallback_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_web_search_does_not_attach_db_fallback_sources",
        "test_scoped_chat_does_not_use_db_fallback_when_vector_search_is_empty",
        "test_scoped_chat_adds_initial_web_sources_to_first_answer_context",
        "test_scoped_chat_can_use_web_search_when_knowledge_base_has_no_hits",
    ]:
        assert test_name not in scoping_source
        assert test_name in fallback_source


def test_knowledge_base_stream_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    stream_test = project_root / "tests" / "test_knowledge_base_streaming.py"

    assert stream_test.exists()
    stream_source = stream_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_stream_requires_owned_knowledge_base",
        "test_scoped_chat_stream_returns_answer_for_owner",
        "test_scoped_chat_stream_json_encodes_thinking",
        "test_scoped_chat_stream_uses_configured_thinking",
        "test_scoped_chat_stream_emits_empty_sources_trailer",
    ]:
        assert test_name not in scoping_source
        assert test_name in stream_source


def test_knowledge_base_scope_build_tests_are_split_from_scoping_file():
    project_root = Path(__file__).resolve().parents[1]
    scoping_source = (
        project_root / "tests" / "test_knowledge_base_scoping.py"
    ).read_text(encoding="utf-8")
    scope_build_test = project_root / "tests" / "test_knowledge_base_scope_build.py"

    assert scope_build_test.exists()
    scope_build_source = scope_build_test.read_text(encoding="utf-8")
    for test_name in [
        "test_scoped_chat_unions_folder_and_explicit_video_scope",
        "test_scoped_search_passes_resolved_video_scope",
        "test_scoped_chat_stream_uses_same_resolved_scope",
        "test_scoped_chat_rejects_external_bvid",
        "test_scope_options_only_returns_current_knowledge_base",
        "test_scope_options_requires_login",
        "test_scope_options_hides_other_users_knowledge_base",
        "test_scoped_build_rejects_unknown_source_binding",
        "test_scoped_build_records_scope_metadata",
        "test_scoped_build_accepts_single_video_selection",
        "test_scoped_build_starts_when_vector_service_is_unavailable",
        "test_scoped_build_rejects_empty_folder_ids",
        "test_scoped_build_rejects_other_users_source_binding",
        "test_build_status_polling_does_not_touch_session_last_seen",
    ]:
        assert test_name not in scoping_source
        assert test_name in scope_build_source
