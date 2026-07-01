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
    compat_service_path = (
        project_root / "app/services/knowledge_base_web_search_compat.py"
    )
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
    assert compat_service_path.exists()
    compat_service_source = compat_service_path.read_text(encoding="utf-8")
    for name in {
        "build_web_search_orchestration_compat",
        "legacy_execute_web_search_tool",
        "legacy_execute_fetch_web_page_tool",
        "legacy_run_initial_web_search",
        "legacy_prepare_web_search_tool_run",
        "legacy_prepare_knowledge_base_web_search",
        "legacy_prepare_knowledge_base_web_search_with_heartbeats",
    }:
        assert f"def {name}" in compat_service_source
    assert "from app.services.knowledge_base_web_search_compat import" in router_source
    assert "def _legacy_execute_web_search_tool" not in router_source
    assert "def _legacy_execute_fetch_web_page_tool" not in router_source
    assert "def _legacy_run_initial_web_search" not in router_source
    assert "def _legacy_prepare_web_search_tool_run" not in router_source
    assert "def _legacy_prepare_knowledge_base_web_search" not in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_knowledge_base_router_uses_services_for_shared_llm_runtime():
    project_root = get_project_root()
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert "from app.routers.chat import" not in router_source
    assert "from app.services.chat_completion import" in router_source
    assert "from app.services.chat_provider_catalog import" in router_source
    assert "from app.services.llm_client import" in router_source
    assert "from app.services.llm_tool_calls import" in router_source
    assert "_get_llm_client" in router_source


def test_knowledge_base_router_delegates_answer_completion_adapter_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_answer_adapter.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def build_complete_knowledge_base_answer" in service_source
    assert "from app.services.knowledge_base_answer_adapter import" in router_source
    assert "complete_llm_answer_resolver" in service_source
    assert "complete_llm_answer_resolver=lambda" in router_source
    assert "_complete_knowledge_base_answer =" in router_source
    assert "async def _complete_knowledge_base_answer" not in router_source
    assert "def complete_llm_with_config" not in router_source
    assert "tool_run.answer is not None" not in router_source
    assert "_prepare_web_search_tool_run" not in declared_names
