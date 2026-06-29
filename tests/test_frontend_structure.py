from pathlib import Path


def test_frontend_structure_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    structure_dir = project_root / "tests" / "frontend_structure"
    expected_files = [
        structure_dir / "test_component_boundaries.py",
        structure_dir / "test_api_boundaries.py",
        structure_dir / "test_style_boundaries.py",
        structure_dir / "test_build_boundaries.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
