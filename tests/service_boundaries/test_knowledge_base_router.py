from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_router_boundary_file_delegates_to_focused_files():
    project_root = get_project_root()
    service_boundary_dir = project_root / "tests" / "service_boundaries"

    for file_name in [
        "test_knowledge_base_router_web_search_boundaries.py",
        "test_knowledge_base_router_catalog_build_boundaries.py",
        "test_knowledge_base_router_chat_search_boundaries.py",
        "test_knowledge_base_delete_boundaries.py",
        "test_rag_ingestion_boundaries.py",
    ]:
        assert (service_boundary_dir / file_name).exists()
