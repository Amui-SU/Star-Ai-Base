import ast

from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import declared_module_names
from tests.service_boundaries.helpers import get_project_root


def function_source(source: str, name: str) -> str:
    module = ast.parse(source)
    for node in module.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return segment
    raise AssertionError(f"{name} not found")


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


def test_knowledge_base_router_delegates_catalog_commands_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_catalog.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def list_workspace_knowledge_bases" in service_source
    assert "async def create_workspace_knowledge_base" in service_source
    assert "from app.services.knowledge_base_catalog import" in router_source
    assert "list_workspace_knowledge_bases(" in router_source
    assert "create_workspace_knowledge_base(" in router_source
    assert "select(KnowledgeBase)" not in router_source
    assert "payload.name.strip()" not in router_source
    assert "KnowledgeBase(" not in router_source
    assert "db.add(knowledge_base)" not in router_source
    assert "await db.refresh(knowledge_base)" not in router_source


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


def test_knowledge_base_router_delegates_scoped_document_loading_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_documents.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "video_cache_matches_favorite",
        "resolve_request_scope",
        "load_db_fallback_documents",
        "load_scoped_chat_documents",
    }
    router_private_names = {
        "_video_cache_matches_favorite",
        "_resolve_request_scope",
        "_load_db_fallback_documents",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.knowledge_base_documents import" in router_source
    assert "async def _load_scoped_chat_documents" in router_source
    assert "load_scoped_chat_documents(" in router_source
    assert "get_rag_service().search_in_knowledge_base(" not in router_source
    assert "VideoCache.description" not in router_source
    assert "resolve_scope_bvids(" not in router_source
    assert declared_names.isdisjoint(router_private_names)


def test_knowledge_base_router_delegates_build_task_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_build_tasks.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    expected_service_names = {
        "run_scoped_build",
        "get_build_status_payload",
    }
    router_private_names = {
        "_run_scoped_build_impl",
    }

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    for name in expected_service_names:
        assert f"def {name}" in service_source or f"async def {name}" in service_source
    assert "from app.services.knowledge_base_build_tasks import" in router_source
    assert "async def _run_scoped_build(" not in router_source
    assert "await _sync_folder(" not in router_source
    assert 'current_step="同步收藏夹..."' not in router_source
    assert (
        "select(IngestionTask).where(IngestionTask.task_id == task_id)"
        not in router_source
    )
    assert declared_names.isdisjoint(router_private_names)


def test_folder_ingestion_delegates_records_and_content_helpers_to_services():
    project_root = get_project_root()
    ingestion_path = project_root / "app/services/folder_ingestion.py"
    records_path = project_root / "app/services/folder_ingestion_records.py"
    content_path = project_root / "app/services/folder_ingestion_content.py"

    ingestion_source = ingestion_path.read_text(encoding="utf-8")

    assert records_path.exists()
    records_source = records_path.read_text(encoding="utf-8")
    for name in {
        "has_cache_scope",
        "get_or_create_folder",
        "get_existing_folder_for_scope",
        "get_video_cache_for_scope",
        "delete_video_vectors_for_scope",
        "upsert_video_cache",
    }:
        assert f"def {name}" in records_source or f"async def {name}" in records_source

    assert content_path.exists()
    content_source = content_path.read_text(encoding="utf-8")
    for name in {
        "extract_video_info",
        "is_better_source",
        "should_refresh_cache",
        "is_asr_cache_usable",
        "video_content_from_cache",
    }:
        assert f"def {name}" in content_source

    assert "from app.services.folder_ingestion_records import" in ingestion_source
    assert "from app.services.folder_ingestion_content import" in ingestion_source
    assert "select(VideoCache)" not in ingestion_source
    assert "VideoCache(" not in ingestion_source
    assert "source_priority =" not in ingestion_source
    assert "def _is_better_source" not in ingestion_source
    assert "def _should_refresh_cache" not in ingestion_source
    assert "def _video_content_from_cache" not in ingestion_source


def test_rag_service_delegates_document_and_filter_helpers_to_services():
    project_root = get_project_root()
    documents_path = project_root / "app/services/rag_documents.py"
    filters_path = project_root / "app/services/rag_filters.py"
    collection_ops_path = project_root / "app/services/rag_collection_ops.py"
    qa_path = project_root / "app/services/rag_qa.py"
    rag_source = (project_root / "app/services/rag.py").read_text(encoding="utf-8")

    assert documents_path.exists()
    documents_source = documents_path.read_text(encoding="utf-8")
    for name in {
        "build_video_content_text",
        "build_video_documents",
    }:
        assert f"def {name}" in documents_source

    assert filters_path.exists()
    filters_source = filters_path.read_text(encoding="utf-8")
    for name in {
        "knowledge_base_filter",
        "video_in_knowledge_base_filter",
    }:
        assert f"def {name}" in filters_source

    assert "from app.services.rag_documents import" in rag_source
    assert "from app.services.rag_filters import" in rag_source
    assert collection_ops_path.exists()
    collection_ops_source = collection_ops_path.read_text(encoding="utf-8")
    for name in {
        "collection_stats",
        "clear_collection",
        "delete_video_vectors",
        "delete_video_vectors_in_knowledge_base",
        "has_video_vectors_in_knowledge_base",
        "delete_knowledge_base_vectors",
    }:
        assert f"def {name}" in collection_ops_source
    assert "from app.services.rag_collection_ops import" in rag_source
    assert qa_path.exists()
    qa_source = qa_path.read_text(encoding="utf-8")
    for name in {
        "answer_rag_question",
        "build_rag_answer_context_and_sources",
        "complete_rag_answer",
        "fallback_rag_answer",
    }:
        assert f"def {name}" in qa_source or f"async def {name}" in qa_source
    assert "from app.services.rag_qa import" in rag_source
    assert "Document(" not in rag_source
    assert "context_parts = []" not in rag_source
    assert "seen_bvids = set()" not in rag_source
    assert '"知识库目前还没有内容"' not in rag_source
    assert "AI 回答时发生错误" not in rag_source
    assert "self.vectorstore._collection.delete(" not in rag_source
    assert "self.vectorstore._collection.get(" not in rag_source
    assert "self.vectorstore._collection.count(" not in rag_source
    assert 'filters = [\n            {"workspace_id": workspace_id}' not in rag_source
    assert '{"bvid": {"$in": normalized_bvids}}' not in rag_source


def test_knowledge_base_router_delegates_build_request_preparation_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_build_requests.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "class KnowledgeBaseBuildPlan" in service_source
    assert "async def prepare_knowledge_base_build_request" in service_source
    assert "from app.services.knowledge_base_build_requests import" in router_source
    assert "prepare_knowledge_base_build_request(" in router_source
    assert "db.get(SourceBinding" not in router_source
    assert "select(SourceCredential)" not in router_source
    assert "decrypt_text(" not in router_source
    assert "create_ingestion_task(" not in router_source
    assert "bilibili_service_from_cookies(" not in router_source
    assert "KnowledgeBaseBuildResponse(" not in router_source


def test_knowledge_base_router_delegates_stats_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_stats.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def build_knowledge_base_stats" in service_source
    assert "from app.services.knowledge_base_stats import" in router_source
    assert "select(func.count(func.distinct(FavoriteVideo.bvid)))" not in router_source
    assert "FavoriteFolder.last_sync_at.isnot(None)" not in router_source


def test_knowledge_base_router_delegates_search_helpers_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_search.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def search_knowledge_base_documents" in service_source
    assert "from app.services.knowledge_base_search import" in router_source
    assert 'detail="Search query cannot be empty"' not in router_source
    assert "rag.search_in_knowledge_base(" not in router_source
    assert "KnowledgeBaseSearchResponse(" not in router_source


def test_knowledge_base_router_delegates_non_streaming_chat_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_chat.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    chat_route_source = function_source(router_source, "chat_with_knowledge_base")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def answer_knowledge_base_chat" in service_source
    assert "from app.services.knowledge_base_chat import" in router_source
    assert "answer_knowledge_base_chat(" in chat_route_source
    assert "_load_scoped_chat_documents(" not in chat_route_source
    assert "resolve_user_llm_credentials(" not in chat_route_source
    assert "_complete_knowledge_base_answer(" not in chat_route_source
    assert "record_usage_event(" not in chat_route_source
    assert "ChatResponse(" not in chat_route_source


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


def test_knowledge_base_router_delegates_streaming_chat_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_chat_stream.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    stream_route_source = function_source(
        router_source, "stream_chat_with_knowledge_base"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "def stream_knowledge_base_chat" in service_source
    assert "from app.services.knowledge_base_chat_stream import" in router_source
    assert "stream_knowledge_base_chat(" in stream_route_source
    assert "async def generate" not in stream_route_source
    assert "_load_scoped_chat_documents(" not in stream_route_source
    assert "resolve_user_llm_credentials(" not in stream_route_source
    assert "_stream_llm_events(" not in stream_route_source
    assert "record_usage_event(" not in stream_route_source
    assert "json.dumps(" not in stream_route_source


def test_knowledge_base_router_delegates_record_deletion_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_delete.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "async def delete_knowledge_base_records" in service_source
    assert "async def delete_knowledge_base" in service_source
    assert "from app.services.knowledge_base_delete import" in router_source
    delete_route_source = function_source(router_source, "delete_knowledge_base")
    assert "delete_knowledge_base_service(" in delete_route_source
    assert "delete_knowledge_base_records(" not in delete_route_source
    assert "delete_by_knowledge_base(" not in delete_route_source
    assert "await db.commit()" not in delete_route_source
    assert "VideoCache.__table__.delete" not in router_source
    assert "FavoriteFolder.__table__.delete" not in router_source
    assert "FavoriteVideo.__table__.delete" not in router_source
    assert "IngestionTask.__table__.delete" not in router_source
    assert "VideoTitleOverride.__table__.delete" not in router_source


def test_favorite_router_uses_shared_default_folder_detection():
    project_root = get_project_root()
    source = (project_root / "app/routers/favorites.py").read_text(encoding="utf-8")

    assert "def _is_default_folder" not in source
    assert "is_legacy_default_favorite_folder" in source
