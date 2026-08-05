"""Contract tests for safe worktree dependency status inspection."""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "worktree-deps.ps1"


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is required for worktree dependency tests")
    return executable


def _checked(args: list[str], cwd: Path, environment: dict[str, str]) -> None:
    run_command(args, cwd, environment, timeout=60)


@pytest.fixture(scope="module")
def repositories(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("worktree deps 路径")
    main = root / "main checkout 主"
    environment = init_repo(main)
    (main / "frontend").mkdir()
    (main / "frontend" / "package.json").write_text(
        '{"name":"fixture"}\n', encoding="utf-8"
    )
    (main / ".gitignore").write_text("frontend/node_modules/\n", encoding="utf-8")
    _checked(["git", "add", "."], main, environment)
    _checked(["git", "commit", "--no-gpg-sign", "-m", "baseline"], main, environment)

    allowed = main / ".worktrees" / "feature tree 功能"
    external = root / "registered elsewhere"
    _checked(
        ["git", "worktree", "add", "-b", "fixture-allowed", str(allowed)],
        main,
        environment,
    )
    _checked(
        ["git", "worktree", "add", "-b", "fixture-external", str(external)],
        main,
        environment,
    )
    return main, allowed, external, environment


def _command(*arguments: str) -> list[str]:
    shell = _powershell()
    command = [shell, "-NoProfile"]
    if Path(shell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    return [*command, "-File", str(SCRIPT), *arguments]


def _run(cwd: Path, environment: dict[str, str], *arguments: str):
    assert SCRIPT.is_file(), "scripts/worktree-deps.ps1 has not been implemented"
    return run_command(_command(*arguments), cwd, environment, timeout=60)


def _failure(cwd: Path, environment: dict[str, str], *arguments: str) -> str:
    with pytest.raises(AssertionError) as caught:
        _run(cwd, environment, *arguments)
    return str(caught.value)


def _status(cwd: Path, environment: dict[str, str], *arguments: str) -> dict[str, str]:
    result = _run(cwd, environment, *arguments)
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    return json.loads(result.stdout)


def test_status_rejects_main_checkout(repositories) -> None:
    main, _, _, environment = repositories

    failure = _failure(main, environment, "-WorktreePath", str(main))

    assert "temporary worktree" in failure.casefold()


def test_status_rejects_unregistered_directory(repositories) -> None:
    main, _, _, environment = repositories
    unregistered = main / ".worktrees" / "unregistered sibling"
    unregistered.mkdir(parents=True)

    failure = _failure(main, environment, "-WorktreePath", str(unregistered))

    assert "registered worktree" in failure.casefold()


def test_status_rejects_registered_worktree_outside_allowed_root(repositories) -> None:
    main, _, external, environment = repositories

    failure = _failure(main, environment, "-WorktreePath", str(external))

    assert "must be inside" in failure.casefold()
    assert ".worktrees" in failure


@pytest.mark.parametrize("arguments", [(), ("-WorktreePath", "")])
def test_default_worktree_path_uses_current_repository(
    repositories, arguments: tuple[str, ...]
) -> None:
    _, allowed, _, environment = repositories

    status = _status(allowed, environment, *arguments)

    assert status["state"] == "missing"
    assert Path(status["worktree"]) == allowed


def test_status_handles_space_and_unicode_worktree_path(repositories) -> None:
    _, allowed, _, environment = repositories

    status = _status(allowed, environment, "-WorktreePath", str(allowed))

    assert Path(status["worktree"]) == allowed
    assert Path(status["dependencyPath"]) == allowed / "frontend" / "node_modules"


@pytest.mark.skipif(os.name != "nt", reason="Windows path comparison contract")
def test_registered_worktree_comparison_is_case_insensitive(repositories) -> None:
    _, allowed, _, environment = repositories
    alternate_case = str(allowed).swapcase()

    status = _status(allowed, environment, "-WorktreePath", alternate_case)

    assert status["state"] == "missing"


def test_sibling_prefix_cannot_escape_allowed_root(repositories) -> None:
    main, _, _, environment = repositories
    sibling = main / ".worktrees-escape"
    _checked(
        ["git", "worktree", "add", "-b", "fixture-prefix", str(sibling)],
        main,
        environment,
    )

    failure = _failure(main, environment, "-WorktreePath", str(sibling))

    assert "must be inside" in failure.casefold()
    assert ".worktrees" in failure


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_status_rejects_reparse_component_between_allowed_root_and_target(
    repositories,
) -> None:
    main, _, _, environment = repositories
    container = main / ".worktrees" / "nested container"
    target = container / "registered nested feature"
    _checked(
        ["git", "worktree", "add", "-b", "fixture-nested", str(target)],
        main,
        environment,
    )
    moved_container = main.parent / "moved nested container"
    container.rename(moved_container)
    _checked(
        ["cmd", "/c", "mklink", "/J", str(container), str(moved_container)],
        main,
        environment,
    )
    try:
        failure = _failure(target, environment, "-WorktreePath", str(target))
        assert "reparse" in failure.casefold() or "boundary" in failure.casefold()
    finally:
        _checked(["cmd", "/c", "rmdir", str(container)], main, environment)
        moved_container.rename(container)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_status_uses_primary_record_with_separate_git_directory(tmp_path: Path) -> None:
    main = tmp_path / "separate metadata main"
    environment = init_repo(main)
    (main / "frontend").mkdir()
    (main / "frontend" / "package.json").write_text(
        '{"name":"separate-fixture"}\n', encoding="utf-8"
    )
    _checked(["git", "add", "."], main, environment)
    _checked(["git", "commit", "--no-gpg-sign", "-m", "baseline"], main, environment)
    isolated_global = tmp_path / "separate-global-config"
    isolated_global.write_text("", encoding="utf-8")
    environment["GIT_CONFIG_GLOBAL"] = str(isolated_global)
    common = tmp_path / "metadata outside main" / "repository.git"
    common.parent.mkdir()
    _checked(
        ["git", "init", "--separate-git-dir", str(common), str(main)],
        tmp_path,
        environment,
    )
    _checked(
        ["git", "--git-dir", str(common), "config", "core.worktree", str(main)],
        tmp_path,
        environment,
    )
    target = main / ".worktrees" / "separate feature"
    _checked(
        ["git", "worktree", "add", "-b", "separate-feature", str(target)],
        main,
        environment,
    )
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir()
    dependency = target / "frontend" / "node_modules"
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(main_modules)],
        target,
        environment,
    )

    try:
        status = _status(target, environment)
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], target, environment)

    assert status["state"] == "shared"
    assert Path(status["worktree"]) == target
    assert Path(status["dependencyPath"]) == target / "frontend" / "node_modules"
    assert Path(status["target"]) == main_modules


@pytest.mark.skipif(os.name != "nt", reason="Windows drive-root contract")
def test_normalize_path_preserves_windows_drive_root(repositories) -> None:
    _, allowed, _, environment = repositories
    escaped_script = str(SCRIPT).replace("'", "''")
    expression = f"""
$tokens = $null
$errors = $null
$source = [IO.File]::ReadAllText('{escaped_script}')
$ast = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
$functionAst = $ast.Find({{
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Normalize-Path'
}}, $true)
if ($null -eq $functionAst) {{ throw 'Normalize-Path function was not found' }}
$pathComparison = [StringComparison]::OrdinalIgnoreCase
$trimSeparators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
Invoke-Expression $functionAst.Extent.Text
$root = [IO.Path]::GetPathRoot([Environment]::SystemDirectory)
[Console]::Out.WriteLine((Normalize-Path $root))
"""
    result = run_command(
        [_powershell(), "-NoProfile", "-Command", expression],
        allowed,
        environment,
        timeout=60,
    )

    expected = Path(os.environ["SystemRoot"]).anchor
    assert result.stdout.strip() == expected


def test_status_reports_missing_isolated_and_unsafe(repositories) -> None:
    _, allowed, _, environment = repositories
    dependency = allowed / "frontend" / "node_modules"

    missing = _status(allowed, environment)
    assert missing["state"] == "missing"
    assert missing["target"] is None
    dependency.mkdir()
    try:
        isolated = _status(allowed, environment)
        assert isolated["state"] == "isolated"
        assert isolated["target"] is None
    finally:
        dependency.rmdir()
    dependency.write_text("not a directory", encoding="utf-8")
    try:
        unsafe = _status(allowed, environment)
        assert unsafe["state"] == "unsafe"
        assert unsafe["target"] is None
    finally:
        dependency.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_status_only_exact_main_node_modules_junction_is_shared(repositories) -> None:
    main, allowed, external, environment = repositories
    source = main / "frontend" / "node_modules"
    source.mkdir(exist_ok=True)
    dependency = allowed / "frontend" / "node_modules"
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(source)],
        allowed,
        environment,
    )
    try:
        shared = _status(allowed, environment)
        assert shared["state"] == "shared"
        assert Path(shared["target"]) == source
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], allowed, environment)

    other = external / "frontend" / "node_modules"
    other.mkdir(exist_ok=True)
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(other)], allowed, environment
    )
    try:
        unsafe = _status(allowed, environment)
        assert unsafe["state"] == "unsafe"
        assert Path(unsafe["target"]) == other
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], allowed, environment)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
@pytest.mark.parametrize("main_state", ["missing", "file", "reparse"])
def test_status_requires_normal_main_node_modules_to_share(
    repositories, main_state: str
) -> None:
    main, allowed, _, environment = repositories
    source = main / "frontend" / "node_modules"
    if source.exists():
        source.rmdir()
    outside = main.parent / f"outside main modules {main_state}"
    if main_state == "file":
        source.write_text("not a directory", encoding="utf-8")
    elif main_state == "reparse":
        outside.mkdir(exist_ok=True)
        _checked(
            ["cmd", "/c", "mklink", "/J", str(source), str(outside)],
            main,
            environment,
        )

    dependency = allowed / "frontend" / "node_modules"
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(source)],
        allowed,
        environment,
    )
    try:
        status = _status(allowed, environment)
        assert status["state"] == "unsafe"
        assert Path(status["target"]) == source
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], allowed, environment)
        if main_state == "file":
            source.unlink()
        elif main_state == "reparse":
            _checked(["cmd", "/c", "rmdir", str(source)], main, environment)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_status_rejects_main_frontend_reparse_for_lexical_target(
    repositories,
) -> None:
    main, allowed, _, environment = repositories
    frontend = main / "frontend"
    saved_frontend = main / "frontend-real-for-boundary-test"
    outside_frontend = main.parent / "outside frontend target"
    outside_modules = outside_frontend / "node_modules"
    outside_modules.mkdir(parents=True, exist_ok=True)
    frontend.rename(saved_frontend)
    _checked(
        ["cmd", "/c", "mklink", "/J", str(frontend), str(outside_frontend)],
        main,
        environment,
    )
    dependency = allowed / "frontend" / "node_modules"
    expected_target = frontend / "node_modules"
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(expected_target)],
        allowed,
        environment,
    )
    try:
        status = _status(allowed, environment)
        assert status["state"] == "unsafe"
        assert Path(status["target"]) == expected_target
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], allowed, environment)
        _checked(["cmd", "/c", "rmdir", str(frontend)], main, environment)
        saved_frontend.rename(frontend)


def _compile_git_shim(directory: Path, environment: dict[str, str]) -> Path:
    source = directory / "GitShim.cs"
    source.write_text(
        r"""
using System;
using System.Diagnostics;
using System.IO;
using System.Text;

public static class GitShim {
    public static int Main(string[] args) {
        bool list = Array.IndexOf(args, "worktree") >= 0 && Array.IndexOf(args, "list") >= 0;
        if (list) {
            int exitCode = Int32.Parse(Environment.GetEnvironmentVariable("GIT_SHIM_EXIT") ?? "0");
            byte[] payload = Convert.FromBase64String(Environment.GetEnvironmentVariable("GIT_SHIM_PAYLOAD") ?? "");
            Console.OpenStandardOutput().Write(payload, 0, payload.Length);
            return exitCode;
        }
        var start = new ProcessStartInfo(Environment.GetEnvironmentVariable("GIT_SHIM_REAL"));
        start.UseShellExecute = false;
        var commandLine = new StringBuilder();
        foreach (string arg in args) {
            if (commandLine.Length > 0) commandLine.Append(' ');
            commandLine.Append('"').Append(arg.Replace("\"", "\\\"")).Append('"');
        }
        start.Arguments = commandLine.ToString();
        var process = Process.Start(start);
        process.WaitForExit();
        return process.ExitCode;
    }
}
""".strip(),
        encoding="utf-8",
    )
    output = directory / "git.exe"
    expression = (
        "Add-Type -Path '"
        + str(source).replace("'", "''")
        + "' -OutputAssembly '"
        + str(output).replace("'", "''")
        + "' -OutputType ConsoleApplication"
    )
    _checked(
        [_powershell(), "-NoProfile", "-Command", expression], directory, environment
    )
    return output


@pytest.fixture(scope="module")
def git_shim(tmp_path_factory: pytest.TempPathFactory, repositories) -> Path:
    if os.name != "nt":
        pytest.skip("Raw malformed Git stream shim is currently Windows-specific")
    directory = tmp_path_factory.mktemp("git-shim")
    return _compile_git_shim(directory, repositories[3])


@pytest.mark.parametrize(
    "payload",
    [b"", b"worktree C:/truncated", b"worktree C:/bad-utf8-\xff\x00"],
    ids=["empty", "truncated", "invalid-utf8"],
)
def test_worktree_list_malformed_streams_fail_closed(
    repositories, git_shim: Path, payload: bytes
) -> None:
    _, allowed, _, base_environment = repositories
    environment = base_environment.copy()
    real_git = shutil.which("git", path=base_environment["PATH"])
    assert real_git is not None
    environment["GIT_SHIM_REAL"] = real_git
    environment["GIT_SHIM_PAYLOAD"] = base64.b64encode(payload).decode("ascii")
    environment["PATH"] = str(git_shim.parent) + os.pathsep + environment["PATH"]

    failure = _failure(allowed, environment)

    assert "worktree" in failure.casefold()


def test_worktree_list_git_failure_fails_closed(repositories, git_shim: Path) -> None:
    _, allowed, _, base_environment = repositories
    environment = base_environment.copy()
    real_git = shutil.which("git", path=base_environment["PATH"])
    assert real_git is not None
    environment.update(
        {
            "GIT_SHIM_REAL": real_git,
            "GIT_SHIM_EXIT": "37",
            "GIT_SHIM_PAYLOAD": "",
            "PATH": str(git_shim.parent) + os.pathsep + environment["PATH"],
        }
    )

    failure = _failure(allowed, environment)

    assert "worktree" in failure.casefold()


@pytest.mark.parametrize("malformation", ["missing-primary", "duplicate-primary"])
def test_status_worktree_records_require_one_primary_first_field(
    repositories, git_shim: Path, malformation: str
) -> None:
    _, allowed, external, base_environment = repositories
    allowed_field = f"worktree {allowed}".encode()
    if malformation == "missing-primary":
        payload = b"HEAD deadbeef\0\0" + allowed_field + b"\0\0"
    else:
        payload = allowed_field + b"\0" + f"worktree {external}".encode() + b"\0\0"
    environment = base_environment.copy()
    real_git = shutil.which("git", path=base_environment["PATH"])
    assert real_git is not None
    environment.update(
        {
            "GIT_SHIM_REAL": real_git,
            "GIT_SHIM_PAYLOAD": base64.b64encode(payload).decode("ascii"),
            "PATH": str(git_shim.parent) + os.pathsep + environment["PATH"],
        }
    )

    failure = _failure(allowed, environment)

    assert "worktree" in failure.casefold() or "primary" in failure.casefold()


def test_prepare_and_detach_are_explicitly_unimplemented(repositories) -> None:
    _, allowed, _, environment = repositories

    for mode in ("Prepare", "Detach"):
        failure = _failure(allowed, environment, "-Mode", mode)
        assert "not implemented" in failure.casefold()
