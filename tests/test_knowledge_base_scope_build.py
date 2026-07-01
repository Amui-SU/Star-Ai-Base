from tests.service_boundaries.helpers import get_project_root


def test_knowledge_base_scope_build_file_delegates_to_focused_files():
    project_root = get_project_root()
    tests_dir = project_root / "tests"

    for file_name in [
        "test_knowledge_base_scope_resolution.py",
        "test_knowledge_base_scope_options.py",
        "test_knowledge_base_build_requests.py",
        "test_knowledge_base_build_status.py",
    ]:
        assert (tests_dir / file_name).exists()
