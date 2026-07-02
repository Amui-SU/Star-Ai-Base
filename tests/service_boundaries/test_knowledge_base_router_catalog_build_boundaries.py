from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import function_source
from tests.service_boundaries.helpers import get_project_root


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


def test_knowledge_base_router_delegates_build_request_preparation_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_build_requests.py"
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    route_runtime_path = (
        project_root / "app/services/knowledge_base_build_route_runtime.py"
    )
    route_runtime_source = route_runtime_path.read_text(encoding="utf-8")
    assert "class KnowledgeBaseBuildPlan" in service_source
    assert "async def prepare_knowledge_base_build_request" in service_source
    assert route_runtime_path.exists()
    assert "from app.services.knowledge_base_build_requests import" not in router_source
    assert (
        "from app.services.knowledge_base_build_requests import" in route_runtime_source
    )
    assert "prepare_knowledge_base_build_request(" not in router_source
    assert "db.get(SourceBinding" not in router_source
    assert "select(SourceCredential)" not in router_source
    assert "decrypt_text(" not in router_source
    assert "create_ingestion_task(" not in router_source
    assert "bilibili_service_from_cookies(" not in router_source
    assert "KnowledgeBaseBuildResponse(" not in router_source


def test_knowledge_base_router_delegates_build_runtime_fallback_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_base_build_runtime.py"
    route_runtime_path = (
        project_root / "app/services/knowledge_base_build_route_runtime.py"
    )
    router_source = (project_root / "app/routers/knowledge_bases.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)
    build_route_source = function_source(router_source, "build_knowledge_base")

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert route_runtime_path.exists()
    route_runtime_source = route_runtime_path.read_text(encoding="utf-8")
    assert "class NoopBuildRAGService" in service_source
    assert "def resolve_build_rag_service" in service_source
    assert "from app.services.knowledge_base_build_runtime import" not in router_source
    assert (
        "from app.services.knowledge_base_build_runtime import" in route_runtime_source
    )
    assert "resolve_build_rag_service" in route_runtime_source
    assert "resolve_rag_service(" in route_runtime_source
    assert "rag_service_factory=get_rag_service" in build_route_source
    assert "_NoopRAGService" not in router_source
    assert "try:" not in build_route_source
    assert "except Exception" not in build_route_source
    assert "logger.warning(" not in build_route_source
    assert "_NoopRAGService" not in declared_names


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
