import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VerifierRepo = tuple[Path, dict[str, str]]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def powershell_executable() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required for verifier CLI contract tests")
    return executable


def isolated_subprocess_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    git_config = tmp_path / "empty.gitconfig"
    git_config.write_text("", encoding="utf-8")
    environment["GIT_CONFIG_GLOBAL"] = str(git_config)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment


def run_checked(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def verifier_repo(tmp_path: Path) -> VerifierRepo:
    repo = tmp_path / "repo"
    environment = isolated_subprocess_environment(tmp_path)
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "scripts" / "verify-fast.ps1", scripts)

    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    (repo / ".gitignore").write_text("frontend/node_modules/\n", encoding="utf-8")
    for command in [
        ["git", "init"],
        ["git", "config", "user.email", "fast-verifier-tests@example.com"],
        ["git", "config", "user.name", "Fast Verifier Tests"],
        ["git", "add", "README.md", ".gitignore"],
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "baseline"],
    ]:
        run_checked(command, repo, environment)

    return repo, environment


def run_verifier(
    repo: Path,
    environment: dict[str, str],
    *arguments: str,
    executable: str | None = None,
) -> subprocess.CompletedProcess[str]:
    shell = executable or powershell_executable()
    command = [shell, "-NoProfile"]
    if Path(shell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", "scripts/verify-fast.ps1", *arguments])
    return subprocess.run(
        command,
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def write_frontend_stub(repo: Path, executable: str) -> Path:
    bin_directory = repo / "frontend" / "node_modules" / ".bin"
    bin_directory.mkdir(parents=True)
    suffix = ".cmd" if os.name == "nt" else ""
    stub = bin_directory / f"{executable}{suffix}"

    if os.name == "nt":
        stub.write_text(
            "@echo off\r\n"
            'echo %* > "%FAST_VERIFIER_LOG%"\r\n'
            "exit /b %FAST_VERIFIER_EXIT%\r\n",
            encoding="utf-8",
        )
    else:
        stub.write_text(
            "#!/bin/sh\n"
            'printf \'%s\\n\' "$@" > "$FAST_VERIFIER_LOG"\n'
            'exit "${FAST_VERIFIER_EXIT:-0}"\n',
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

    return stub


def test_agent_instructions_define_the_micro_task_fast_lane():
    instructions = read("AGENTS.md")
    compact_instructions = " ".join(instructions.split())

    assert "## Task Risk Tiers" in instructions
    assert "### Micro task fast lane" in instructions
    assert "at most three production files" in instructions
    assert "scripts\\verify-fast.ps1" in instructions
    assert "docs/micro-task-template.md" in instructions
    assert (
        "at least one relevant `-BackendTest`, `-FrontendTest`, `-LintFile`, or "
        "`-StaticFile` target" in compact_instructions
    )
    assert "comma-separated values" in compact_instructions
    assert (
        "`-StaticFile` is only for documentation or style files" in compact_instructions
    )
    assert "unstaged, staged, and untracked changes" in compact_instructions
    assert (
        "replaces steps 2 and 3 of the Stable Commit Workflow" in compact_instructions
    )
    assert "independently committable changeset" in compact_instructions
    assert (
        "authorized by the user or required by the integration workflow"
        in compact_instructions
    )
    assert (
        "target files overlap existing changes or verification shares mutable state"
        in compact_instructions
    )


def test_micro_task_template_keeps_the_record_concise():
    template = read("docs/micro-task-template.md")

    for field in ["Change", "Acceptance", "Verification"]:
        assert f"**{field}:**" in template

    assert "independent design spec" in template
    assert "implementation plan" in template
    assert "Optional when this is a bug: **Root cause:**" in template
    assert "Optional when scope could easily expand: **Out of scope:**" in template
    assert "Problem" not in template


def test_workflow_source_exempts_qualified_micro_tasks_from_full_steps():
    instructions = read("AGENTS.md")
    compact_instructions = " ".join(instructions.split())

    assert (
        "## Stable Commit Workflow (normal, high-risk, release, and escalated work)"
        in instructions
    )
    assert (
        "Qualified micro tasks use `scripts\\verify-fast.ps1` instead of steps 2 and 3."
        in compact_instructions
    )
    assert (
        "For normal, high-risk, release, or escalated work, run the full commit "
        "verification before committing." in compact_instructions
    )
    assert "verify-before-commit.ps1 -Format" in instructions


def test_workflow_source_delegates_claude_task_rules_to_agents():
    claude = read("CLAUDE.md")

    assert (
        "Task classification, worktree choice, and verification rules are defined only in "
        "`AGENTS.md`." in claude.splitlines()[:8]
    )


def test_fast_lane_boundaries_mark_v2_as_the_current_policy():
    design = read("docs/superpowers/specs/2026-07-28-micro-task-fast-lane-design.md")

    assert "> **Status:** Superseded on conflict details by V2." in design
    assert "[V2 design](2026-07-29-micro-task-fast-lane-v2-design.md)" in design
    assert "`-StaticFile` is only for documentation or style files" in design
    assert "comma-separated values" in design
    assert "unstaged, staged, and untracked" in design
    assert "any dirty checkout" not in design
    assert "one commit" not in design
    assert "six-line task record" not in design


def test_fast_verifier_only_runs_explicit_targets():
    script = read("scripts/verify-fast.ps1")

    for parameter in ["FrontendTest", "LintFile", "BackendTest", "StaticFile"]:
        assert f"[string[]]${parameter}" in script

    assert 'Invoke-Step "git diff --check"' in script
    assert "node_modules/.bin/vitest" in script
    assert "node_modules/.bin/eslint" in script
    assert "& $vitest run @FrontendTest" in script
    assert "& $eslint @LintFile" in script
    assert "python -m pytest -q @BackendTest" in script
    assert "Provide at least one targeted check" in script
    assert "npm test" not in script
    assert "npx eslint" not in script
    assert "npm run build" not in script
    assert 'Invoke-Step "frontend tests"' not in script
    assert 'Invoke-Step "backend tests"' not in script


def test_untracked_scan_uses_streaming_file_apis():
    script = read("scripts/verify-fast.ps1")

    assert "[System.IO.File]::ReadAllBytes" not in script
    assert "System.IO.FileStream" in script
    assert "System.IO.StreamReader" in script
    assert "StandardOutput.BaseStream" in script
    assert "ls-files -z --others --exclude-standard" in script


def test_fast_lane_preserves_full_verification_boundaries():
    instructions = read("AGENTS.md")
    compact_instructions = " ".join(instructions.split())

    assert (
        "`scripts/verify-before-commit.ps1` remains required for normal or high-risk work"
        in compact_instructions
    )
    for boundary in ["authentication", "security", "dependencies", "deployment"]:
        assert boundary in instructions


def test_comma_separated_backend_targets_run_each_file(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_one.py").write_text(
        "def test_one():\n    assert True\n", encoding="utf-8"
    )
    (tests / "test_two.py").write_text(
        "def test_two():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-BackendTest",
        "tests/test_one.py,tests/test_two.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout
    assert "targeted frontend tests" not in result.stdout


@pytest.mark.parametrize("static_file", ["docs/note.md", "styles/fix.css"])
def test_static_file_accepts_supported_extensions(
    verifier_repo: VerifierRepo, static_file: str
):
    repo, environment = verifier_repo
    target = repo / static_file
    target.parent.mkdir()
    target.write_text("content\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", static_file)

    assert result.returncode == 0, result.stdout + result.stderr


def test_static_file_rejects_unsupported_extensions(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "unsafe.py").write_text("print('unsafe')\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "unsafe.py")

    assert result.returncode != 0
    assert "Unsupported static file" in result.stdout + result.stderr


def test_unstaged_whitespace_in_tracked_static_file_fails(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_text("baseline\ninvalid \n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    assert result.returncode != 0


def test_staged_whitespace_in_tracked_static_file_fails(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_text("baseline\ninvalid \n", encoding="utf-8")
    run_checked(["git", "add", "README.md"], repo, environment)

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    assert result.returncode != 0


def test_untracked_whitespace_in_static_file_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("invalid \n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "trailing whitespace" in result.stdout + result.stderr


def test_untracked_terminal_blank_line_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md" in result.stdout + result.stderr
    assert "blank line" in result.stdout + result.stderr


def test_untracked_file_containing_only_one_newline_is_a_terminal_blank_line(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"\n")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "terminal blank line" in result.stdout + result.stderr


def test_untracked_conflict_marker_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("<<<<<<< HEAD\ncontent\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


@pytest.mark.parametrize(
    "marker",
    [
        "<<<<<<<<< branch",
        "========",
        ">>>>>>>> branch",
        "||||||| base",
    ],
)
def test_untracked_extended_conflict_marker_fails(
    verifier_repo: VerifierRepo, marker: str
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text(f"{marker}\ncontent\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


def test_untracked_conflict_marker_requires_the_whole_line(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("prefix <<<<<<< HEAD suffix\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode == 0, result.stdout + result.stderr


def test_untracked_utf8_bom_conflict_marker_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"\xef\xbb\xbf<<<<<<< HEAD\ncontent\n")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


def test_untracked_binary_file_with_nul_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"binary\x00invalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode == 0, result.stdout + result.stderr


def test_untracked_invalid_utf8_file_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"\xffinvalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode == 0, result.stdout + result.stderr


def test_large_untracked_text_file_reports_late_whitespace(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    large_content = ("valid line\n" * 300_000) + "invalid \n"
    (repo / "large.txt").write_text(large_content, encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "large.txt")

    assert result.returncode != 0
    assert "large.txt:300001" in result.stdout + result.stderr
    assert "trailing whitespace" in result.stdout + result.stderr


def test_untracked_special_character_path_is_enumerated_without_git_quoting(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    relative_path = Path("中文 空格 'quoted'") / "nested" / "note.md"
    target = repo / relative_path
    target.parent.mkdir(parents=True)
    target.write_text("invalid \n", encoding="utf-8")
    windows_powershell = shutil.which("powershell") if os.name == "nt" else None

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        str(relative_path),
        executable=windows_powershell,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert ":1 trailing whitespace" in output
    assert "Could not read untracked file" not in output


def test_untracked_symbolic_link_is_rejected_without_scanning_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    outside = repo.parent / "outside-note.md"
    outside.write_text("invalid \n", encoding="utf-8")
    link = repo / "linked-note.md"
    try:
        link.symlink_to(outside)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "linked-note.md" in output
    assert "symbolic link or reparse point" in output
    assert "trailing whitespace" not in output


def test_static_file_rejects_case_variant_sibling_on_case_sensitive_filesystem(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    case_probe = repo.parent / "case-sensitivity-probe"
    case_probe.write_text("probe\n", encoding="utf-8")
    if (repo.parent / "CASE-SENSITIVITY-PROBE").exists():
        pytest.skip("case-insensitive filesystem")

    outside = repo.parent / "REPO"
    outside.mkdir()
    (outside / "outside.md").write_text("outside\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "../REPO/outside.md")

    assert result.returncode != 0
    assert "Static file must stay within project root" in result.stdout + result.stderr


def test_static_file_rejects_symbolic_link_to_outside_repo(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    outside = repo.parent / "outside"
    outside.mkdir()
    (outside / "outside.md").write_text("outside\n", encoding="utf-8")
    link = repo / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise

    result = run_verifier(repo, environment, "-StaticFile", "linked/outside.md")

    assert result.returncode != 0
    assert (
        "Static file path cannot contain a symbolic link"
        in result.stdout + result.stderr
    )


def test_frontend_test_uses_local_vitest_with_expanded_targets(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    write_frontend_stub(repo, "vitest")
    log = tmp_path / "vitest-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-FrontendTest",
        "src/one.test.ts,src/two.test.ts",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == [
        "run",
        "src/one.test.ts",
        "src/two.test.ts",
    ]


def test_lint_file_uses_local_eslint_with_target(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-LintFile", "src/widget.ts")

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == ["src/widget.ts"]


@pytest.mark.parametrize(
    ("option", "executable", "target", "step"),
    [
        ("-FrontendTest", "vitest", "src/one.test.ts", "targeted frontend tests"),
        ("-LintFile", "eslint", "src/widget.ts", "targeted frontend lint"),
    ],
)
def test_frontend_executable_failure_propagates_exit_code(
    verifier_repo: VerifierRepo,
    tmp_path: Path,
    option: str,
    executable: str,
    target: str,
    step: str,
):
    repo, environment = verifier_repo
    write_frontend_stub(repo, executable)
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "23"

    result = run_verifier(repo, environment, option, target)

    assert result.returncode == 23, result.stdout + result.stderr
    assert f"[FAIL] {step} failed" in result.stdout


@pytest.mark.parametrize("option", ["-FrontendTest", "-LintFile"])
def test_missing_frontend_executable_has_clear_error(
    verifier_repo: VerifierRepo, option: str
):
    repo, environment = verifier_repo
    (repo / "frontend").mkdir()

    result = run_verifier(repo, environment, option, "src/target.ts")

    assert result.returncode != 0
    assert "Missing frontend dependency:" in result.stdout + result.stderr


def test_positional_target_is_not_bound_to_another_verifier_option(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_one.py").write_text(
        "def test_one():\n    assert True\n", encoding="utf-8"
    )
    (tests / "test_two.py").write_text(
        "def test_two():\n    assert True\n", encoding="utf-8"
    )
    (repo / "frontend").mkdir()

    result = run_verifier(
        repo,
        environment,
        "-BackendTest",
        "tests/test_one.py",
        "tests/test_two.py",
    )

    assert result.returncode != 0
    assert "targeted frontend tests" not in result.stdout
