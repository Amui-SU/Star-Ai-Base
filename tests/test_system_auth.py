from pathlib import Path


def test_system_auth_tests_delegate_to_focused_files():
    project_root = Path(__file__).resolve().parents[1]
    system_auth_dir = project_root / "tests" / "system_auth"
    expected_files = [
        system_auth_dir / "test_account_sessions.py",
        system_auth_dir / "test_admin_users.py",
        system_auth_dir / "test_email_codes.py",
        system_auth_dir / "test_oauth_google.py",
        system_auth_dir / "test_oauth_providers.py",
        system_auth_dir / "test_email_config.py",
    ]

    for expected_file in expected_files:
        assert expected_file.exists()

    source_line_count = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    assert source_line_count <= 80
