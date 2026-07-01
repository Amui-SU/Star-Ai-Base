from tests.service_boundaries.helpers import get_project_root


def test_knowledge_scope_file_delegates_to_focused_files():
    project_root = get_project_root()
    focused_dir = project_root / "tests" / "knowledge_scope"

    for file_name in [
        "test_catalog.py",
        "test_rag_filters.py",
        "test_delete_cleanup.py",
        "test_db_fallback.py",
    ]:
        assert (focused_dir / file_name).exists()
