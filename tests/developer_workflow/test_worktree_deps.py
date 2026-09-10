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
    (main / "frontend" / "package-lock.json").write_text(
        '{"name":"fixture","lockfileVersion":3}\n', encoding="utf-8"
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


def test_status_runs_under_powershell_core(repositories) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell Core is required for the cross-platform contract")
    _, allowed, _, environment = repositories

    result = run_command(
        [pwsh, "-NoProfile", "-File", str(SCRIPT), "-WorktreePath", str(allowed)],
        allowed,
        environment,
        timeout=60,
    )

    assert result.stderr == ""
    status = json.loads(result.stdout)
    assert Path(status["worktree"]) == allowed


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


def _compile_tool_shims(directory: Path, environment: dict[str, str]) -> Path:
    source = directory / "ToolShim.cs"
    source.write_text(
        r"""
using System;
using System.IO;
using System.Text;

public static class ToolShim {
    public static int Main(string[] args) {
        string tool = Environment.GetEnvironmentVariable("TOOL_SHIM_NAME");
        if (String.IsNullOrEmpty(tool)) {
            tool = Path.GetFileNameWithoutExtension(Environment.GetCommandLineArgs()[0]).ToLowerInvariant();
        }
        string log = Environment.GetEnvironmentVariable("TOOL_SHIM_LOG");
        using (var writer = new StreamWriter(log, true, new UTF8Encoding(false))) {
            writer.Write(tool);
            writer.Write('\t');
            writer.Write(Convert.ToBase64String(Encoding.UTF8.GetBytes(Environment.CurrentDirectory)));
            foreach (string arg in args) {
                writer.Write('\t');
                writer.Write(Convert.ToBase64String(Encoding.UTF8.GetBytes(arg)));
            }
            writer.WriteLine();
        }
        string exitName = tool.ToUpperInvariant() + "_SHIM_EXIT";
        int exitCode = Int32.Parse(Environment.GetEnvironmentVariable(exitName) ?? "0");
        if (tool == "node" && exitCode == 0) Console.WriteLine("v22.0.0");
        if (tool == "npm" && exitCode == 0) Console.WriteLine("{}");
        string createDirectory = Environment.GetEnvironmentVariable("NPM_SHIM_CREATE_DIRECTORY");
        if (tool == "npm" && !String.IsNullOrEmpty(createDirectory)) {
            Directory.CreateDirectory(createDirectory);
        }
        string replaceDirectory = Environment.GetEnvironmentVariable("NPM_SHIM_REPLACE_DIRECTORY_WITH_FILE");
        if (tool == "npm" && !String.IsNullOrEmpty(replaceDirectory)) {
            Directory.Delete(replaceDirectory);
            File.WriteAllText(replaceDirectory, "changed concurrently");
        }
        if (exitCode != 0) Console.Error.WriteLine(tool + " fixture failure");
        return exitCode;
    }
}
""".strip(),
        encoding="utf-8",
    )
    output = directory / "tool-template.exe"
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
    shutil.copy2(output, directory / "node.exe")
    shutil.copy2(output, directory / "npm.exe")
    return directory


@pytest.fixture(scope="module")
def tool_shims(tmp_path_factory: pytest.TempPathFactory, repositories) -> Path:
    if os.name != "nt":
        pytest.skip("Native node/npm shim contract is Windows-specific")
    directory = tmp_path_factory.mktemp("worktree-tool-shims")
    return _compile_tool_shims(directory, repositories[3])


def _tool_environment(
    base_environment: dict[str, str],
    tool_shims: Path,
    log: Path,
    *,
    include_node: bool = True,
    include_npm: bool = True,
    npm_cmd: bool = False,
) -> dict[str, str]:
    directory = log.parent / f"tools-{log.stem}"
    directory.mkdir(exist_ok=True)
    if include_node:
        shutil.copy2(tool_shims / "node.exe", directory / "node.exe")
    if include_npm:
        if npm_cmd:
            shutil.copy2(tool_shims / "tool-template.exe", directory / "npm-tool.exe")
            (directory / "npm.cmd").write_text(
                '@set "TOOL_SHIM_NAME=npm"\r\n@"%~dp0npm-tool.exe" %*\r\n',
                encoding="utf-8",
            )
        else:
            shutil.copy2(tool_shims / "npm.exe", directory / "npm.exe")
    real_git = shutil.which("git", path=base_environment["PATH"])
    assert real_git is not None
    environment = base_environment.copy()
    environment.update(
        {
            "PATH": str(directory) + os.pathsep + str(Path(real_git).parent),
            "TOOL_SHIM_LOG": str(log),
        }
    )
    return environment


def _tool_calls(log: Path) -> list[tuple[str, Path, list[str]]]:
    if not log.exists():
        return []
    calls = []
    for line in log.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        calls.append(
            (
                fields[0],
                Path(base64.b64decode(fields[1]).decode("utf-8")),
                [base64.b64decode(value).decode("utf-8") for value in fields[2:]],
            )
        )
    return calls


def _add_prepare_worktree(main: Path, environment: dict[str, str], name: str) -> Path:
    target = main / ".worktrees" / name
    _checked(
        ["git", "worktree", "add", "-b", f"prepare-{name}", str(target)],
        main,
        environment,
    )
    return target


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_prepare_reuses_compatible_main_dependencies_idempotently(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "prepare-compatible")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    log = tmp_path / "compatible-tools.log"
    environment = _tool_environment(base_environment, tool_shims, log)

    first = _status(target, environment, "-Mode", "Prepare")
    first_calls = _tool_calls(log)
    second = _status(target, environment, "-Mode", "Prepare")

    assert first["state"] == "shared"
    assert second == first
    assert Path(first["target"]) == main_modules
    assert (target / "frontend" / "node_modules").is_dir()
    assert _tool_calls(log) == first_calls
    assert first_calls == [
        ("node", target, ["--version"]),
        ("npm", main / "frontend", ["ls", "--depth=0", "--json"]),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows line-ending contract")
def test_prepare_treats_git_normalized_manifest_line_endings_as_compatible(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    _checked(["git", "config", "core.autocrlf", "true"], main, base_environment)
    main_lock = main / "frontend" / "package-lock.json"
    original_main_lock = main_lock.read_bytes()
    main_lock.write_bytes(main_lock.read_bytes().replace(b"\r\n", b"\n"))
    target = _add_prepare_worktree(main, base_environment, "prepare-crlf-compatible")
    target_lock = target / "frontend" / "package-lock.json"
    assert main_lock.read_bytes() != target_lock.read_bytes()
    _checked(
        ["git", "diff", "--quiet", "--", "frontend/package-lock.json"],
        target,
        base_environment,
    )
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    log = tmp_path / "compatible-crlf-tools.log"
    environment = _tool_environment(base_environment, tool_shims, log)

    try:
        status = _status(target, environment, "-Mode", "Prepare")

        assert status["state"] == "shared"
        assert _tool_calls(log) == [
            ("node", target, ["--version"]),
            ("npm", main / "frontend", ["ls", "--depth=0", "--json"]),
        ]
    finally:
        main_lock.write_bytes(original_main_lock)
        _checked(["git", "config", "--unset", "core.autocrlf"], main, base_environment)
        dependency = target / "frontend" / "node_modules"
        if os.path.lexists(dependency):
            _status(target, environment, "-Mode", "Detach")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_prepare_preserves_existing_isolated_dependencies_without_tools(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "prepare-isolated")
    dependency = target / "frontend" / "node_modules"
    dependency.mkdir()
    marker = dependency / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    log = tmp_path / "isolated-tools.log"
    environment = _tool_environment(base_environment, tool_shims, log)

    status = _status(target, environment, "-Mode", "Prepare")

    assert status["state"] == "isolated"
    assert marker.read_text(encoding="utf-8") == "keep"
    assert _tool_calls(log) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows npm.cmd contract")
def test_prepare_accepts_direct_npm_cmd_entry(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "prepare-npm-cmd")
    (main / "frontend" / "node_modules").mkdir(exist_ok=True)
    log = tmp_path / "npm-cmd-tools.log"
    environment = _tool_environment(base_environment, tool_shims, log, npm_cmd=True)

    status = _status(target, environment, "-Mode", "Prepare")

    assert status["state"] == "shared"
    assert _tool_calls(log)[-1] == (
        "npm",
        main / "frontend",
        ["ls", "--depth=0", "--json"],
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
@pytest.mark.parametrize(
    "failure_case",
    [
        "node-missing",
        "npm-missing",
        "node-failure",
        "manifest-missing",
        "manifest-git-symlink",
        "manifest-reparse",
        "npm-failure",
        "concurrent-isolated",
        "main-changed-after-proof",
    ],
)
def test_prepare_incompatible_or_unsafe_inputs_fail_without_creating_junction(
    repositories, tool_shims: Path, tmp_path: Path, failure_case: str
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, f"failure-{failure_case}")
    main_modules = main / "frontend" / "node_modules"
    outside = main.parent / f"outside-{failure_case}"
    main_modules.mkdir(exist_ok=True)
    log = tmp_path / f"{failure_case}.log"
    environment = _tool_environment(
        base_environment,
        tool_shims,
        log,
        include_node=failure_case != "node-missing",
        include_npm=failure_case != "npm-missing",
    )
    cleanup: list[tuple[str, Path]] = []
    if failure_case == "node-failure":
        environment["NODE_SHIM_EXIT"] = "9"
    elif failure_case == "manifest-missing":
        (target / "frontend" / "package-lock.json").unlink()
    elif failure_case == "manifest-git-symlink":
        manifest = target / "frontend" / "package.json"
        symlink_blob = target / "symlink-target.txt"
        symlink_blob.write_text("../package.json", encoding="utf-8")
        hash_result = run_command(
            ["git", "hash-object", "-w", str(symlink_blob)],
            target,
            base_environment,
            timeout=60,
        )
        _checked(
            [
                "git",
                "update-index",
                "--cacheinfo",
                f"120000,{hash_result.stdout.strip()},frontend/package.json",
            ],
            target,
            base_environment,
        )
        manifest.write_text("../package.json", encoding="utf-8")
    elif failure_case == "manifest-reparse":
        manifest = target / "frontend" / "package.json"
        manifest.unlink()
        outside.mkdir(exist_ok=True)
        _checked(
            ["cmd", "/c", "mklink", "/J", str(manifest), str(outside)],
            target,
            environment,
        )
        cleanup.append(("junction", manifest))
    elif failure_case == "npm-failure":
        environment["NPM_SHIM_EXIT"] = "17"
    elif failure_case == "concurrent-isolated":
        environment["NPM_SHIM_CREATE_DIRECTORY"] = str(
            target / "frontend" / "node_modules"
        )
    elif failure_case == "main-changed-after-proof":
        environment["NPM_SHIM_REPLACE_DIRECTORY_WITH_FILE"] = str(main_modules)
        cleanup.append(("file", main_modules))

    try:
        failure = _failure(target, environment, "-Mode", "Prepare")
        assert "isolated" in failure.casefold() or "unsafe" in failure.casefold()
        dependency = target / "frontend" / "node_modules"
        if failure_case == "concurrent-isolated":
            assert dependency.is_dir()
            assert not dependency.is_symlink()
        else:
            assert not os.path.lexists(dependency)
        npm_calls = [call for call in _tool_calls(log) if call[0] == "npm"]
        expected_arguments = {
            "node-missing": [["ci"]],
            "npm-missing": [],
            "node-failure": [["ci"]],
            "manifest-missing": [],
            "manifest-git-symlink": [],
            "manifest-reparse": [],
            "npm-failure": [["ls", "--depth=0", "--json"], ["ci"]],
            "concurrent-isolated": [["ls", "--depth=0", "--json"]],
            "main-changed-after-proof": [["ls", "--depth=0", "--json"]],
        }
        assert [call[2] for call in npm_calls] == expected_arguments[failure_case]
        assert all(call[2] not in (["install"], ["npx"]) for call in npm_calls)
        if failure_case == "npm-failure":
            assert "not implemented yet" not in failure.casefold()
    finally:
        for kind, path in reversed(cleanup):
            if kind == "junction":
                _checked(["cmd", "/c", "rmdir", str(path)], main, environment)
            else:
                path.unlink()


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


@pytest.mark.skipif(os.name != "nt", reason="Windows isolated fallback contract")
@pytest.mark.parametrize(
    "mismatch", ["package", "lock", "missing-main", "invalid-main", "reparse-main"]
)
def test_prepare_uses_isolated_npm_ci_when_reuse_is_incompatible(
    repositories, tool_shims: Path, tmp_path: Path, mismatch: str
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, f"fallback-{mismatch}")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    dependency = target / "frontend" / "node_modules"
    log = tmp_path / f"fallback-{mismatch}.log"
    environment = _tool_environment(base_environment, tool_shims, log)
    environment["NPM_SHIM_CREATE_DIRECTORY"] = str(dependency)

    restore_main = False
    if mismatch == "package":
        (target / "frontend" / "package.json").write_text(
            '{"name":"isolated-package"}\n', encoding="utf-8"
        )
    elif mismatch == "lock":
        (target / "frontend" / "package-lock.json").write_text(
            '{"name":"isolated-lock","lockfileVersion":3}\n', encoding="utf-8"
        )
    elif mismatch == "missing-main":
        main_modules.rmdir()
        restore_main = True
    elif mismatch == "invalid-main":
        main_modules.rmdir()
        main_modules.write_text("not a directory", encoding="utf-8")
        restore_main = True
    else:
        outside = main.parent / "outside-fallback-reparse-main"
        main_modules.rmdir()
        outside.mkdir(exist_ok=True)
        _checked(
            ["cmd", "/c", "mklink", "/J", str(main_modules), str(outside)],
            main,
            environment,
        )
        restore_main = True

    try:
        status = _status(target, environment, "-Mode", "Prepare")

        assert status["state"] == "isolated"
        assert dependency.is_dir()
        assert not dependency.is_symlink()
        assert _tool_calls(log) == [("npm", target / "frontend", ["ci"])]
    finally:
        if restore_main:
            if mismatch == "reparse-main":
                _checked(["cmd", "/c", "rmdir", str(main_modules)], main, environment)
            elif main_modules.is_file():
                main_modules.unlink()
            main_modules.mkdir(exist_ok=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_manifest_change_detaches_shared_link_before_isolated_install(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "fallback-shared-change")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    sentinel = main_modules / "must-survive-shared-fallback.txt"
    sentinel.write_text("safe", encoding="utf-8")
    dependency = target / "frontend" / "node_modules"
    first_log = tmp_path / "fallback-shared-first.log"
    first_environment = _tool_environment(base_environment, tool_shims, first_log)
    assert _status(target, first_environment, "-Mode", "Prepare")["state"] == "shared"

    (target / "frontend" / "package.json").write_text(
        '{"name":"changed-after-share"}\n', encoding="utf-8"
    )
    fallback_log = tmp_path / "fallback-shared-second.log"
    fallback_environment = _tool_environment(base_environment, tool_shims, fallback_log)
    fallback_environment["NPM_SHIM_CREATE_DIRECTORY"] = str(dependency)

    status = _status(target, fallback_environment, "-Mode", "Prepare")

    assert status["state"] == "isolated"
    assert dependency.is_dir()
    assert not dependency.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "safe"
    assert _tool_calls(fallback_log) == [("npm", target / "frontend", ["ci"])]


@pytest.mark.skipif(os.name != "nt", reason="Windows isolated fallback contract")
def test_prepare_rejects_non_directory_output_from_successful_npm_ci(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "fallback-output-file")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    (target / "frontend" / "package.json").write_text(
        '{"name":"force-isolated-output"}\n', encoding="utf-8"
    )
    dependency = target / "frontend" / "node_modules"
    log = tmp_path / "fallback-output-file.log"
    environment = _tool_environment(base_environment, tool_shims, log)
    environment["NPM_SHIM_CREATE_DIRECTORY"] = str(dependency)
    environment["NPM_SHIM_REPLACE_DIRECTORY_WITH_FILE"] = str(dependency)

    failure = _failure(target, environment, "-Mode", "Prepare")

    assert "normal directory" in failure.casefold()
    assert dependency.is_file()
    assert dependency.read_text(encoding="utf-8") == "changed concurrently"
    assert _tool_calls(log) == [("npm", target / "frontend", ["ci"])]


def test_dependency_helper_avoids_recursive_or_implicit_dependency_commands() -> None:
    source = SCRIPT.read_text(encoding="utf-8").casefold()

    assert "remove-item" not in source
    assert "cmd /c rmdir" not in source
    assert 'invoke-checkedtool $npm @("install")' not in source
    assert 'invoke-checkedtool $npm @("npx")' not in source


def test_worktree_policy_requires_dependency_detach_before_cleanup() -> None:
    policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "worktree-deps.ps1 -Mode Prepare" in policy
    assert "worktree-deps.ps1 -Mode Status" in policy
    assert "worktree-deps.ps1 -Mode Detach" in policy
    assert policy.index("-Mode Detach") < policy.index("git worktree remove")


def test_micro_task_template_forbids_dependency_mutation_while_shared() -> None:
    template = (PROJECT_ROOT / "docs" / "micro-task-template.md").read_text(
        encoding="utf-8"
    )
    lowered = template.casefold()

    assert "worktree-deps.ps1 -Mode Prepare" in template
    assert "worktree-deps.ps1 -Mode Detach" in template
    assert "shared" in lowered
    assert "npm install" in lowered
    assert "npm ci" in lowered
    assert lowered.index("-mode detach") < lowered.index("git worktree remove")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_detach_removes_verified_link_but_preserves_main_sentinel(
    repositories, tool_shims: Path, tmp_path: Path
) -> None:
    main, _, _, base_environment = repositories
    target = _add_prepare_worktree(main, base_environment, "detach-shared")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    sentinel = main_modules / "must-survive-detach.txt"
    sentinel.write_text("safe", encoding="utf-8")
    dependency = target / "frontend" / "node_modules"
    log = tmp_path / "detach-shared.log"
    environment = _tool_environment(base_environment, tool_shims, log)
    assert _status(target, environment, "-Mode", "Prepare")["state"] == "shared"

    status = _status(target, environment, "-Mode", "Detach")

    assert status["state"] == "missing"
    assert not os.path.lexists(dependency)
    assert sentinel.read_text(encoding="utf-8") == "safe"


def test_detach_missing_is_idempotent(repositories) -> None:
    main, _, _, environment = repositories
    target = _add_prepare_worktree(main, environment, "detach-missing")

    status = _status(target, environment, "-Mode", "Detach")

    assert status["state"] == "missing"


def test_detach_refuses_normal_directory_and_preserves_contents(repositories) -> None:
    main, _, _, environment = repositories
    target = _add_prepare_worktree(main, environment, "detach-isolated")
    dependency = target / "frontend" / "node_modules"
    dependency.mkdir(exist_ok=True)
    marker = dependency / "owned.txt"
    marker.write_text("keep", encoding="utf-8")

    failure = _failure(target, environment, "-Mode", "Detach")

    assert "verified junction" in failure.casefold()
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_detach_refuses_unexpected_junction_and_preserves_both_targets(
    repositories, tmp_path: Path
) -> None:
    main, _, _, environment = repositories
    target = _add_prepare_worktree(main, environment, "detach-unexpected")
    dependency = target / "frontend" / "node_modules"
    unexpected = tmp_path / "unexpected-modules"
    unexpected.mkdir()
    unexpected_marker = unexpected / "unexpected.txt"
    unexpected_marker.write_text("keep", encoding="utf-8")
    main_modules = main / "frontend" / "node_modules"
    main_modules.mkdir(exist_ok=True)
    main_marker = main_modules / "main.txt"
    main_marker.write_text("keep", encoding="utf-8")
    _checked(
        ["cmd", "/c", "mklink", "/J", str(dependency), str(unexpected)],
        target,
        environment,
    )

    try:
        failure = _failure(target, environment, "-Mode", "Detach")

        assert "verified junction" in failure.casefold()
        assert os.path.lexists(dependency)
        assert unexpected_marker.read_text(encoding="utf-8") == "keep"
        assert main_marker.read_text(encoding="utf-8") == "keep"
    finally:
        _checked(["cmd", "/c", "rmdir", str(dependency)], target, environment)
