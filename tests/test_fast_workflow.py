import os
import re
import signal
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VerifierRepo = tuple[Path, dict[str, str]]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def markdown_section(document: str, heading: str) -> str:
    marker = heading.split(maxsplit=1)[0]
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", document)
    assert match is not None, f"missing Markdown section: {heading}"
    remainder = document[match.end() :]
    next_heading = re.search(rf"(?m)^#{{1,{len(marker)}}}\s+", remainder)
    if next_heading is None:
        return remainder
    return remainder[: next_heading.start()]


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


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except Exception:
        pass

    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        pass

    try:
        process.wait(timeout=5)
    except Exception:
        pass


def run_subprocess_with_timeout(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    popen_options: dict[str, object] = {}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **popen_options,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        raise AssertionError(
            f"subprocess timed out after {timeout_seconds}s: "
            f"args={command!r}\nstdout={stdout!r}\nstderr={stderr!r}"
        ) from None

    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )


def test_timed_subprocess_kills_child_process_tree_and_reports_diagnostics(
    tmp_path: Path,
):
    sentinel = tmp_path / "child-survived.txt"
    child_code = (
        "import pathlib,sys,time; "
        "time.sleep(0.8); "
        "pathlib.Path(sys.argv[1]).write_text('survived', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]]); "
        "print('parent-started', flush=True); "
        "time.sleep(10)"
    )
    command = [sys.executable, "-c", parent_code, child_code, str(sentinel)]

    started = time.monotonic()
    with pytest.raises(AssertionError) as error:
        run_subprocess_with_timeout(
            command,
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout_seconds=0.1,
        )
    elapsed = time.monotonic() - started

    time.sleep(1)
    diagnostic = str(error.value)
    assert elapsed < 5
    assert not sentinel.exists()
    assert repr(command) in diagnostic
    assert "parent-started" in diagnostic
    assert "stdout=" in diagnostic
    assert "stderr=" in diagnostic


@pytest.mark.parametrize(
    "taskkill_error",
    [
        pytest.param(
            subprocess.TimeoutExpired(["taskkill"], 10),
            id="timeout",
        ),
        pytest.param(OSError("taskkill unavailable"), id="os-error"),
        pytest.param(RuntimeError("taskkill failed unexpectedly"), id="unexpected"),
    ],
)
def test_windows_process_tree_cleanup_falls_back_when_taskkill_fails(
    monkeypatch: pytest.MonkeyPatch, taskkill_error: Exception
):
    calls: list[object] = []

    class FakeProcess:
        pid = 1234

        def poll(self):
            return None

        def kill(self):
            calls.append("kill")

        def wait(self, timeout):
            calls.append(("wait", timeout))

    def fail_taskkill(*args, **kwargs):
        raise taskkill_error

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(subprocess, "run", fail_taskkill)

    terminate_process_tree(FakeProcess())

    assert calls == ["kill", ("wait", 5)]


def run_checked(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    result = run_subprocess_with_timeout(
        command,
        cwd=cwd,
        environment=environment,
        timeout_seconds=20,
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
        ["git", "add", "README.md", ".gitignore", "scripts/verify-fast.ps1"],
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
    return run_subprocess_with_timeout(
        command,
        cwd=repo,
        environment=environment,
        timeout_seconds=60,
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


def write_frontend_target(repo: Path, relative_path: str) -> Path:
    target = repo / "frontend" / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("export {};\n", encoding="utf-8")
    return target


def test_agent_instructions_define_the_micro_task_fast_lane():
    instructions = read("AGENTS.md")
    fast_lane = markdown_section(instructions, "### Micro task fast lane")

    assert "## Task Risk Tiers" in instructions
    assert "### Micro task fast lane" in instructions
    assert "at most three production files" in instructions
    assert "scripts\\verify-fast.ps1" in instructions
    assert "docs/micro-task-template.md" in instructions
    assert (
        "at least one relevant `-BackendTest`, `-FrontendTest`, `-LintFile`, or "
        "`-StaticFile` target" in " ".join(fast_lane.split())
    )
    for token in [
        "comma-separated values",
        "unstaged, staged, and untracked changes",
        "independently committable changeset",
        "target files overlap existing changes",
        "verification shares mutable state",
    ]:
        assert token in " ".join(fast_lane.split())


def test_fast_lane_maps_file_types_to_specific_verification_targets():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split())
        for token in [
            "Python production",
            "`-BackendTest`",
            "Black",
            "changed Python",
            "JavaScript or TypeScript production",
            "`-LintFile`",
            "every changed code file",
            "`-FrontendTest`",
            "behavior",
            "`-StaticFile`",
            "manual check",
            "`-StaticFile` supports only Markdown, plain text, CSS, SCSS, and Less",
            "HTML, JSON, YAML, and YML require complete verification",
            "shared build",
            "deployment",
            "authentication",
            "security",
            "complete verification",
        ]:
            assert token.casefold() in compact.casefold()


def test_fast_lane_requires_concrete_verification_evidence():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    template = read("docs/micro-task-template.md")

    for document in [fast_lane, template]:
        compact = " ".join(document.split())
        assert "actual command" in compact
        assert "specific targets" in compact
        assert "manual results" in compact
        assert "“verified”" in compact


def test_fast_lane_mapping_applies_regardless_of_mixed_targets():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split()).casefold()
        for token in [
            "every changed static file",
            "regardless of other targets",
            "every changed frontend",
            "unsupported changed files",
            "complete verification",
        ]:
            assert token.casefold() in compact


def test_task_file_policy_scopes_only_non_overlapping_dirty_changes():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split()).casefold()
        for token in [
            "`-TaskFile`",
            "clean or isolated checkout",
            "omit",
            "all changed files",
            "unrelated non-overlapping dirty changes",
            "list every task file",
            "actual command",
            "not a verification target",
            "target files overlap existing changes",
            "verification shares mutable state",
            "worktree",
        ]:
            assert token.casefold() in compact

    assert "-TaskFile AGENTS.md,docs/micro-task-template.md" in fast_lane
    assert "-StaticFile AGENTS.md,docs/micro-task-template.md" in fast_lane


def test_micro_task_template_keeps_the_record_concise():
    template = read("docs/micro-task-template.md")

    for field in ["Change", "Acceptance", "Verification"]:
        assert f"**{field}:**" in template

    assert "independent design spec" in template
    assert "implementation plan" in template
    assert "Optional when this is a bug: **Root cause:**" in template
    assert "Optional when scope could easily expand: **Out of scope:**" in template


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
    assert "[`AGENTS.md`](../../../AGENTS.md)" in design
    assert (
        PROJECT_ROOT
        / "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    ).is_file()


def test_fast_verifier_only_runs_explicit_targets():
    script = read("scripts/verify-fast.ps1")

    for parameter in [
        "FrontendTest",
        "LintFile",
        "BackendTest",
        "StaticFile",
        "TaskFile",
    ]:
        assert f"[string[]]${parameter}" in script

    assert 'Invoke-Step "git diff --check"' in script
    assert "node_modules/.bin/vitest" in script
    assert "node_modules/.bin/eslint" in script
    assert "& $vitest run @($frontendTestTargetsVerified.ToArray())" in script
    assert "& $eslint -- @($lintTargetsVerified.ToArray())" in script
    assert "python -m pytest -q -- @($backendTargetsVerified.ToArray())" in script
    assert "Provide at least one targeted check" in script
    assert "npm test" not in script
    assert "npx eslint" not in script
    assert "npm run build" not in script
    assert 'Invoke-Step "frontend tests"' not in script
    assert 'Invoke-Step "backend tests"' not in script

    extension_list = re.search(r"\$allowedStaticExtensions\s*=\s*@\(([^)]*)\)", script)
    assert extension_list is not None
    assert set(re.findall(r'"(\.[a-z]+)"', extension_list.group(1))) == {
        ".md",
        ".txt",
        ".css",
        ".scss",
        ".less",
    }


def test_untracked_scan_uses_streaming_file_apis():
    script = read("scripts/verify-fast.ps1")

    assert "[System.IO.File]::ReadAllBytes" not in script
    assert "System.IO.FileStream" in script
    assert "System.IO.StreamReader" in script
    assert "StandardOutput.BaseStream" in script
    assert "ls-files -z --others --exclude-standard" in script


def test_fast_lane_preserves_full_verification_boundaries():
    instructions = read("AGENTS.md")
    high_risk = markdown_section(instructions, "### High-risk task")
    boundaries = markdown_section(instructions, "### Full verification boundaries")

    for token in [
        "authentication",
        "security",
        "dependencies",
        "deployment",
        "complete verification",
    ]:
        assert token in high_risk
    for token in [
        "normal",
        "high-risk",
        "release",
        "authentication",
        "security",
        "dependency",
        "deployment",
        "complete verification",
    ]:
        assert token.casefold() in boundaries.casefold()


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
    target.parent.mkdir(parents=True)
    target.write_text("content\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", static_file)

    assert result.returncode == 0, result.stdout + result.stderr


def test_static_file_rejects_unsupported_extensions(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "unsafe.py").write_text("print('unsafe')\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "unsafe.py")

    assert result.returncode != 0
    assert "Unsupported static file" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("static_file", "content"),
    [
        ("package.json", b"{}\n"),
        ("compose.yml", b"services: {}\n"),
        (".github/workflows/ci.yaml", b"name: ci\n"),
        ("page.html", b"<p>content</p>\n"),
    ],
)
def test_static_file_rejects_structured_and_config_files(
    verifier_repo: VerifierRepo, static_file: str, content: bytes
):
    repo, environment = verifier_repo
    target = repo / static_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    result = run_verifier(repo, environment, "-StaticFile", static_file)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert f"Unsupported static file: {static_file}" in output
    assert "use full verification" in output


@pytest.mark.parametrize(
    ("git_state", "code_path"),
    [("untracked", "change.py"), ("unstaged", "frontend/widget.tsx")],
)
def test_static_file_requires_changed_target_when_only_code_changed(
    verifier_repo: VerifierRepo, git_state: str, code_path: str
):
    repo, environment = verifier_repo
    target = repo / code_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if git_state == "unstaged":
        target.write_bytes(b"export const value = 1;\n")
        run_checked(["git", "add", code_path], repo, environment)
        run_checked(
            [
                "git",
                "commit",
                "--no-gpg-sign",
                "--no-verify",
                "-m",
                "track code target",
            ],
            repo,
            environment,
        )
    target.write_bytes(b"changed\n")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Static file target is not changed: README.md" in output


def test_static_file_requires_its_target_to_be_changed(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Static file target is not changed: README.md" in output


def test_static_only_verification_rejects_code_hidden_by_changed_readme(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "change.py").write_text("changed\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Changed Python files require at least one -BackendTest target: change.py"
        in output
    )


def test_static_only_verification_requires_every_changed_static_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n", encoding="utf-8")
    (repo / "style.css").write_text("body {}\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -StaticFile target for changed file: style.css" in output


def test_static_only_verification_accepts_all_changed_static_files(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n", encoding="utf-8")
    (repo / "style.css").write_text("body {}\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md,style.css")

    assert result.returncode == 0, result.stdout + result.stderr


def test_task_file_scope_ignores_unrelated_untracked_configuration(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "settings.toml").write_bytes(b"enabled = true \n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_task_file_must_be_changed(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "unrelated.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Task file is not changed: README.md" in output


def test_task_file_scope_still_requires_lint_for_changed_typescript(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    target = repo / "frontend" / "src" / "widget.ts"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"export const value = 1;\n")
    write_frontend_target(repo, "src/widget.test.ts")
    write_frontend_stub(repo, "vitest")
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "vitest-arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "frontend/src/widget.ts",
        "-FrontendTest",
        "src/widget.test.ts",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -LintFile target for changed frontend file: src/widget.ts" in output


def test_omitting_task_file_keeps_full_changed_worktree_mapping(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "settings.toml").write_bytes(b"enabled = true\n")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "settings.toml" in output
    assert "use full verification" in output


@pytest.mark.parametrize("git_state", ["unstaged", "staged", "untracked"])
def test_task_file_scope_rejects_whitespace_in_each_git_state(
    verifier_repo: VerifierRepo, git_state: str
):
    repo, environment = verifier_repo
    relative_path = "README.md" if git_state != "untracked" else "note.md"
    (repo / relative_path).write_bytes(b"invalid \n")
    if git_state == "staged":
        run_checked(["git", "add", relative_path], repo, environment)

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        relative_path,
        "-StaticFile",
        relative_path,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "trailing whitespace" in output


def test_task_file_scope_supports_untracked_unicode_path(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    relative_path = "中文 空格/说明.md"
    target = repo / relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes("内容\n".encode())
    (repo / "settings.toml").write_bytes(b"enabled = true\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        relative_path,
        "-StaticFile",
        relative_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_task_file_rejects_normalized_duplicates(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md,.\\README.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Duplicate task file: .\\README.md" in output


def test_task_file_must_stay_within_repository(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "../outside.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Task file must stay within project root: ../outside.md" in output


def test_task_file_does_not_count_as_a_verification_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(repo, environment, "-TaskFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Provide at least one targeted check" in output


def test_backend_target_cannot_hide_missing_lint_for_changed_frontend_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    frontend_file = repo / "frontend" / "src" / "widget.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_bytes(b"export const value = 2;\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")
    write_frontend_target(repo, "src/widget.tsx")

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        "README.md",
        "-BackendTest",
        "tests/test_probe.py",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Missing -LintFile target for changed frontend file: src/widget.tsx" in output
    )


def test_mixed_targets_continue_when_static_backend_and_lint_mapping_is_complete(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    frontend_file = repo / "frontend" / "src" / "widget.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_bytes(b"export const value = 2;\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")
    write_frontend_target(repo, "src/widget.tsx")
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        "README.md",
        "-BackendTest",
        "tests/test_probe.py",
        "-LintFile",
        "src/widget.tsx",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == ["--", "src/widget.tsx"]


def test_changed_python_requires_backend_target_even_with_frontend_target(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "change.py").write_bytes(b"value = 2\n")
    write_frontend_target(repo, "src/unrelated.test.ts")
    write_frontend_stub(repo, "vitest")
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "vitest-arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-FrontendTest", "src/unrelated.test.ts")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Changed Python files require at least one -BackendTest target: change.py"
        in output
    )


def test_changed_static_file_requires_target_even_with_backend_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"content\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -StaticFile target for changed file: note.md" in output


def test_unsupported_changed_extension_requires_full_verification(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "settings.toml").write_bytes(b"enabled = true\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Fast verification does not support changed file: settings.toml; "
        "use full verification." in output
    )


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


@pytest.mark.parametrize(
    ("encoding", "bom"),
    [
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ],
)
def test_static_file_rejects_utf16_bom_without_nul(
    verifier_repo: VerifierRepo, encoding: str, bom: bytes
):
    repo, environment = verifier_repo
    payload = bom + "\u1234\u5678".encode(encoding)
    assert b"\x00" not in payload
    (repo / "note.md").write_bytes(payload)

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "UTF-8" in result.stdout + result.stderr


def test_untracked_binary_file_with_nul_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"binary\x00invalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode != 0
    assert "NUL" in result.stdout + result.stderr


def test_untracked_invalid_utf8_file_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"\xffinvalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode != 0
    assert "UTF-8" in result.stdout + result.stderr


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
    assert "symbolic link" in (result.stdout + result.stderr).casefold()


def test_frontend_test_uses_local_vitest_with_expanded_targets(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    write_frontend_target(repo, "src/one.test.ts")
    write_frontend_target(repo, "src/two.test.ts")
    write_frontend_stub(repo, "vitest")
    log = tmp_path / "vitest-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
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
    write_frontend_target(repo, "src/widget.ts")
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-LintFile", "src/widget.ts")

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == ["--", "src/widget.ts"]


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
    (repo / "README.md").write_bytes(b"changed\n")
    write_frontend_target(repo, target)
    write_frontend_stub(repo, executable)
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "23"

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
        option,
        target,
    )

    assert result.returncode == 23, result.stdout + result.stderr
    assert f"[FAIL] {step} failed" in result.stdout


@pytest.mark.parametrize("option", ["-FrontendTest", "-LintFile"])
def test_missing_frontend_executable_has_clear_error(
    verifier_repo: VerifierRepo, option: str
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    target = "src/target.test.ts" if option == "-FrontendTest" else "src/target.ts"
    write_frontend_target(repo, target)

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
        option,
        target,
    )

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


@pytest.mark.parametrize(
    ("option", "executable", "safe_target", "injected_target"),
    [
        ("-BackendTest", None, "tests/test_probe.py", "--collect-only"),
        ("-FrontendTest", "vitest", "src/probe.test.ts", "--passWithNoTests"),
        ("-LintFile", "eslint", "src/probe.ts", "--fix"),
    ],
)
def test_tool_targets_reject_comma_expanded_option_injection(
    verifier_repo: VerifierRepo,
    tmp_path: Path,
    option: str,
    executable: str | None,
    safe_target: str,
    injected_target: str,
):
    repo, environment = verifier_repo
    target = repo / ("frontend" if option != "-BackendTest" else "") / safe_target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (
            "def test_probe():\n    assert True\n"
            if target.suffix == ".py"
            else "export {};\n"
        ),
        encoding="utf-8",
    )
    if executable is not None:
        write_frontend_stub(repo, executable)
        environment["FAST_VERIFIER_LOG"] = str(tmp_path / "tool-arguments.txt")
        environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, option, f"{safe_target},{injected_target}")

    assert result.returncode != 0
    assert "must not start with '-'" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("option", "target"),
    [
        ("-BackendTest", "../outside.py"),
        ("-BackendTest", "does-not-exist.py"),
        ("-FrontendTest", "../outside.test.ts"),
        ("-LintFile", "does-not-exist.ts"),
    ],
)
def test_tool_targets_require_existing_non_traversing_relative_files(
    verifier_repo: VerifierRepo, option: str, target: str
):
    repo, environment = verifier_repo
    result = run_verifier(repo, environment, option, target)

    assert result.returncode != 0
    assert "target" in (result.stdout + result.stderr).casefold()


def test_backend_target_allows_a_node_id_after_a_verified_python_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo, environment, "-BackendTest", "tests/test_probe.py::test_probe"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_task_file_rejects_a_code_symbolic_link_before_verification(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    linked = repo / "linked.py"
    try:
        linked.symlink_to(outside)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "linked.py",
        "-BackendTest",
        "tests/test_probe.py",
    )

    assert result.returncode != 0
    assert "symbolic link" in (result.stdout + result.stderr).casefold()


@pytest.mark.parametrize(
    ("option", "repo_relative_path", "verifier_target"),
    [
        pytest.param("-BackendTest", "linked.py", "linked.py", id="backend"),
        pytest.param(
            "-FrontendTest",
            "frontend/src/linked.test.ts",
            "src/linked.test.ts",
            id="frontend",
        ),
        pytest.param("-LintFile", "frontend/src/linked.ts", "src/linked.ts", id="lint"),
        pytest.param("-TaskFile", "linked.py", "linked.py", id="code-task-file"),
    ],
)
def test_code_targets_reject_git_index_mode_120000(
    verifier_repo: VerifierRepo,
    option: str,
    repo_relative_path: str,
    verifier_target: str,
):
    repo, environment = verifier_repo
    target = repo / repo_relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("outside-target", encoding="utf-8")
    blob = run_subprocess_with_timeout(
        ["git", "hash-object", "-w", repo_relative_path],
        cwd=repo,
        environment=environment,
        timeout_seconds=20,
    )
    assert blob.returncode == 0, blob.stdout + blob.stderr
    run_checked(
        [
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{blob.stdout.strip()},{repo_relative_path}",
        ],
        repo,
        environment,
    )

    arguments = [option, verifier_target]
    if option == "-TaskFile":
        backend_test = repo / "tests" / "test_probe.py"
        backend_test.parent.mkdir()
        backend_test.write_text(
            "def test_probe():\n    assert True\n", encoding="utf-8"
        )
        arguments.extend(["-BackendTest", "tests/test_probe.py"])

    result = run_verifier(repo, environment, *arguments)

    assert result.returncode != 0
    assert "Git symbolic link" in result.stdout + result.stderr


def test_changed_python_is_black_checked_before_backend_tests(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "change.py").write_text("value=1\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    assert result.returncode != 0
    assert "changed Python formatting" in result.stdout
    assert "targeted backend tests" not in result.stdout


def test_black_checks_all_scoped_python_files(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "one.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "two.py").write_text("other = 2\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "one.py,two.py",
        "-BackendTest",
        "tests/test_probe.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 files would be left unchanged" in result.stdout + result.stderr


@pytest.mark.parametrize("git_state", ["unstaged", "staged"])
def test_task_file_diff_check_treats_brackets_as_literal_pathspecs(
    verifier_repo: VerifierRepo, git_state: str
):
    repo, environment = verifier_repo
    path = repo / "[ab].md"
    path.write_text("invalid \n", encoding="utf-8")
    run_checked(["git", "add", "-N", "[ab].md"], repo, environment)
    if git_state == "staged":
        run_checked(["git", "add", "[ab].md"], repo, environment)

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "[ab].md",
        "-StaticFile",
        "[ab].md",
    )

    assert result.returncode != 0
    assert "trailing whitespace" in result.stdout + result.stderr


def test_static_file_checks_each_case_distinct_changed_file_on_case_sensitive_filesystem(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "Foo.md").write_text("one\n", encoding="utf-8")
    if (repo / "foo.md").exists():
        pytest.skip("case-insensitive filesystem")
    (repo / "foo.md").write_text("two\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "Foo.md")

    assert result.returncode != 0
    assert "foo.md" in result.stdout + result.stderr
