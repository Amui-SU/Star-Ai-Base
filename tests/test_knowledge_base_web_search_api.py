from pathlib import Path


def test_knowledge_base_web_search_api_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    api_dir = project_root / "tests" / "knowledge_base_web_search_api"
    expected_files = [
        api_dir / "test_tool_chain.py",
        api_dir / "test_fetch_page.py",
        api_dir / "test_toggle_fallback.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
