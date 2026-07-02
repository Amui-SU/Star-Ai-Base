from tests.service_boundaries.helpers import declared_callable_names
from tests.service_boundaries.helpers import get_project_root


def test_legacy_knowledge_router_delegates_runtime_to_service():
    project_root = get_project_root()
    service_path = project_root / "app/services/knowledge_legacy_runtime.py"
    router_source = (project_root / "app/routers/knowledge.py").read_text(
        encoding="utf-8"
    )
    declared_names = declared_callable_names(router_source)

    assert service_path.exists()
    service_source = service_path.read_text(encoding="utf-8")
    assert "build_tasks:" in service_source
    for name in {
        "get_collection_stats_without_embeddings",
        "get_legacy_folder_status",
        "sync_legacy_folders",
        "start_legacy_build_task_for_session",
        "start_legacy_build_task",
        "run_legacy_build_task",
        "get_legacy_build_status",
        "clear_legacy_knowledge_base",
        "delete_legacy_video_from_knowledge",
    }:
        assert f"def {name}" in service_source

    assert "from app.services.knowledge_legacy_runtime import" in router_source
    assert "session={}" not in router_source
    assert "get_collection_stats_without_embeddings" not in declared_names
    assert "_build_knowledge_base_task" not in declared_names
    assert "select(UserSession.bili_mid)" not in router_source
    assert "FavoriteFolder.session_id.in_" not in router_source
    assert "bilibili_service_from_cookies(" not in router_source
    assert "ContentFetcher(" not in router_source
    assert "await _sync_folder(" not in router_source
    assert "uuid.uuid4()" not in router_source
    assert "get_db_context()" not in router_source
    assert "rag.clear_collection()" not in router_source
    assert "rag.delete_video(" not in router_source
