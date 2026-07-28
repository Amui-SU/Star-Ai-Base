from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_agent_instructions_define_the_micro_task_fast_lane():
    instructions = read("AGENTS.md")

    assert "## Task Risk Tiers" in instructions
    assert "### Micro task fast lane" in instructions
    assert "at most three production files" in instructions
    assert "scripts\\verify-fast.ps1" in instructions
    assert "docs/micro-task-template.md" in instructions
    assert "use a worktree" in instructions


def test_micro_task_template_keeps_the_record_concise():
    template = read("docs/micro-task-template.md")

    for field in [
        "Problem",
        "Root cause",
        "Change",
        "Out of scope",
        "Acceptance",
        "Verification",
    ]:
        assert f"**{field}:**" in template

    assert "independent design spec" in template
    assert "implementation plan" in template


def test_fast_verifier_only_runs_explicit_targets():
    script = read("scripts/verify-fast.ps1")

    for parameter in ["FrontendTest", "LintFile", "BackendTest"]:
        assert f"[string[]]${parameter}" in script

    assert 'Invoke-Step "git diff --check"' in script
    assert "npm test -- --run @FrontendTest" in script
    assert "npx eslint @LintFile" in script
    assert "python -m pytest -q @BackendTest" in script
    assert "Provide at least one targeted check" in script
    assert "npm run build" not in script
    assert 'Invoke-Step "frontend tests"' not in script
    assert 'Invoke-Step "backend tests"' not in script


def test_fast_lane_preserves_full_verification_boundaries():
    instructions = read("AGENTS.md")

    assert "does not replace `scripts/verify-before-commit.ps1`" in instructions
    for boundary in ["authentication", "security", "dependencies", "deployment"]:
        assert boundary in instructions
