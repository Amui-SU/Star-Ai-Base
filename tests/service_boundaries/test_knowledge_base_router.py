from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import declared_module_names
from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_delegates_web_search_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_web_search.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_module_names(router_source)

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
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_web_search_orchestration.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_module_names(router_source)

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
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_presenters.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

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
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_messages.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

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
    project_root = get_project_root()
    source = (project_root / "app/routers/favorites.py").read_text(encoding="utf-8")

    assert "def _is_default_folder" not in source
    assert "is_legacy_default_favorite_folder" in source
