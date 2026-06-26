import configparser
from pathlib import Path


def test_github_actions_ci_runs_backend_and_frontend_quality_gates():
    project_root = Path(__file__).resolve().parents[1]
    workflow = project_root / ".github" / "workflows" / "ci.yml"

    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
    for required in [
        "python -m pytest -q",
        "npm ci",
        "npm run lint",
        "npm test",
        "npm run build",
    ]:
        assert required in content


def test_pytest_asyncio_fixture_loop_scope_is_explicit():
    config = configparser.ConfigParser()
    read_files = config.read(Path(__file__).resolve().parents[1] / "pytest.ini")

    assert read_files
    assert config.get("pytest", "asyncio_default_fixture_loop_scope") == "function"


def test_pytest_warning_filters_only_known_upstream_multipart_warning():
    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().parents[1] / "pytest.ini")

    filters = "\n".join(
        value
        for key, value in config.items("pytest")
        if key.startswith("filterwarnings")
    )

    assert "Please use `import python_multipart` instead." in filters
    assert "starlette.formparsers" in filters
