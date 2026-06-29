from pathlib import Path


def test_knowledge_base_web_search_streaming_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    streaming_dir = project_root / "tests" / "knowledge_base_web_search_streaming"
    expected_files = [
        streaming_dir / "test_stream_status.py",
        streaming_dir / "test_stream_heartbeats.py",
        streaming_dir / "test_stream_sources.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
