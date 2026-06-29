from pathlib import Path


def test_chat_thinking_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    chat_thinking_dir = project_root / "tests" / "chat_thinking"
    expected_files = [
        chat_thinking_dir / "test_request_models.py",
        chat_thinking_dir / "test_configuration.py",
        chat_thinking_dir / "test_native_reasoning.py",
        chat_thinking_dir / "test_tool_calls.py",
        chat_thinking_dir / "test_tool_call_limits.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
