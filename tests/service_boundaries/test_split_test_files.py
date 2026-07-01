from tests.service_boundaries.helpers import get_project_root


def test_split_test_files_delegate_to_focused_guard_files():
    project_root = get_project_root()
    service_boundary_dir = project_root / "tests" / "service_boundaries"
    split_guard_dir = service_boundary_dir / "split_guards"

    for file_name in [
        "test_knowledge_web_search_split_files.py",
        "test_knowledge_scope_split_files.py",
        "test_backend_service_split_files.py",
    ]:
        assert (split_guard_dir / file_name).exists()

    source = (service_boundary_dir / "test_split_test_files.py").read_text(
        encoding="utf-8"
    )
    assert len(source.splitlines()) <= 80
