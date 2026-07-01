from .helpers import get_project_root


def test_frontend_style_boundary_tests_are_split_by_domain():
    project_root = get_project_root()
    style_boundary_dir = project_root / "tests" / "frontend_structure"
    original_file = style_boundary_dir / "test_style_boundaries.py"

    expected_files = [
        "test_global_style_boundaries.py",
        "test_workspace_account_source_style_boundaries.py",
        "test_chat_import_style_boundaries.py",
    ]
    for file_name in expected_files:
        assert (style_boundary_dir / file_name).exists()

    original_source = original_file.read_text(encoding="utf-8")
    assert original_source.count("def test_") <= 2
