from pathlib import Path


def test_service_boundary_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    boundaries_dir = project_root / "tests" / "service_boundaries"
    expected_files = [
        boundaries_dir / "test_router_package.py",
        boundaries_dir / "test_chat_router.py",
        boundaries_dir / "test_web_search_service.py",
        boundaries_dir / "test_knowledge_base_router.py",
        boundaries_dir / "test_auth_database_ingestion.py",
        boundaries_dir / "test_split_test_files.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
