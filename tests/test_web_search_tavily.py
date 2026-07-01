from tests.service_boundaries.helpers import get_project_root


def test_web_search_tavily_file_delegates_to_focused_files():
    project_root = get_project_root()
    focused_dir = project_root / "tests" / "web_search_tavily"

    for file_name in [
        "test_success_paths.py",
        "test_overrides.py",
        "test_fallbacks_and_failures.py",
    ]:
        assert (focused_dir / file_name).exists()
