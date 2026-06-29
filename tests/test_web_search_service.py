from pathlib import Path


def test_web_search_service_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    service_dir = project_root / "tests" / "web_search_service"
    expected_files = [
        service_dir / "test_fetch_page.py",
        service_dir / "test_provider_fallbacks.py",
        service_dir / "test_proxy_dns_safety.py",
        service_dir / "test_diagnostics.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
