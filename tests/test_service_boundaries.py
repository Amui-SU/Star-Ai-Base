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

    assert streaming_test.exists()
    streaming_source = streaming_test.read_text(encoding="utf-8")
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

    assert api_test.exists()
    api_source = api_test.read_text(encoding="utf-8")
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
        assert test_name in api_source
