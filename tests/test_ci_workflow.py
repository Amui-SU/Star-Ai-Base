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
