import os
import re
import shutil
import stat
import subprocess
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
    assert log.read_text(encoding="utf-8").split() == ["src/widget.tsx"]


def test_changed_python_requires_backend_target_even_with_frontend_target(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "change.py").write_bytes(b"value = 2\n")
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
