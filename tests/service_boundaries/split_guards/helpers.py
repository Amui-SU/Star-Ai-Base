from pathlib import Path

from tests.service_boundaries.helpers import get_project_root


def project_tests_dir() -> Path:
    return get_project_root() / "tests"


def service_boundary_dir() -> Path:
    return project_tests_dir() / "service_boundaries"


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_optional_source(path: Path) -> str:
    return read_source(path) if path.exists() else ""


def combined_source(paths: list[Path]) -> str:
    return "\n".join(read_source(path) for path in paths)


def assert_test_names_moved(
    *,
    mixed_source: str,
    focused_source: str,
    test_names: list[str],
):
    for test_name in test_names:
        assert test_name not in mixed_source
        assert test_name in focused_source


def assert_focused_files_contain_tests(
    *,
    mixed_source: str,
    focused_files: dict[str, list[str]],
    focused_dir: Path,
):
    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        assert_test_names_moved(
            mixed_source=mixed_source,
            focused_source=read_source(focused_path),
            test_names=test_names,
        )
