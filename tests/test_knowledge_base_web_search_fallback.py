from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_web_search_fallback_file_delegates_to_focused_files():
    project_root = get_project_root()
    focused_dir = project_root / "tests" / "knowledge_base_web_search_fallback"

    for file_name in [
        "test_db_fallback_isolation.py",
        "test_initial_web_context.py",
        "test_web_only_answer.py",
    ]:
        assert (focused_dir / file_name).exists()
