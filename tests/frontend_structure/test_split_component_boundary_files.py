from .helpers import get_project_root


def test_frontend_component_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    component_boundary_dir = project_root / "tests" / "frontend_structure"
    original_file = component_boundary_dir / "test_component_boundaries.py"

    expected_files = [
        "test_chat_component_boundaries.py",
        "test_account_import_component_boundaries.py",
        "test_auth_sources_workspace_component_boundaries.py",
    ]
    for file_name in expected_files:
        assert (component_boundary_dir / file_name).exists()

    original_source = original_file.read_text(encoding="utf-8")
    assert original_source.count("def test_") <= 2
