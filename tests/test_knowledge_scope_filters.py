from pathlib import Path


def test_knowledge_scope_filter_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    filters_dir = project_root / "tests" / "knowledge_scope_filters"
    expected_files = [
        filters_dir / "test_request_models.py",
        filters_dir / "test_list_scope_options.py",
        filters_dir / "test_resolve_scope_bvids.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
