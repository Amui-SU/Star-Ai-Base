"""Contract tests for deterministic staged-file verification."""

from __future__ import annotations

import base64
import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_SOURCE = PROJECT_ROOT / "scripts" / "verify-staged.ps1"
WEB_EXTENSIONS = (
    "js",
    "ts",
    "jsx",
    "tsx",
    "json",
    "css",
    "scss",
    "less",
    "html",
    "md",
    "yaml",
    "yml",
)
_WINDOWS_GIT_SHIM: Path | None = None


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required for staged verifier contract tests")
    return executable


def _checked(args: list[str], repo: Path, environment: dict[str, str]) -> None:
    run_command(args, repo, environment)


def _prepare_repo(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    assert SCRIPT_SOURCE.is_file(), "scripts/verify-staged.ps1 has not been implemented"

    repo = tmp_path / "repo"
    environment = init_repo(repo)
    scripts = repo / "scripts"
    scripts.mkdir()
    shutil.copy2(SCRIPT_SOURCE, scripts / SCRIPT_SOURCE.name)

    log_path = repo / ".tool-calls.jsonl"
    environment["STAGED_VERIFY_LOG"] = str(log_path)
    environment["STAGED_VERIFY_BLACK_EXIT"] = "0"
    environment["STAGED_VERIFY_BLACK_STDERR"] = ""
    environment["STAGED_VERIFY_PRETTIER_EXIT"] = "0"
    environment["STAGED_VERIFY_PYTHON"] = sys.executable

    fake_modules = repo / ".test-tools"
    black_module = fake_modules / "black"
    black_module.mkdir(parents=True)
    (black_module / "__init__.py").write_text("", encoding="utf-8")
    (black_module / "__main__.py").write_text(
        """import json
import os
import sys

record = {"tool": "black", "argv": sys.argv[1:], "cwd": os.getcwd()}
with open(os.environ["STAGED_VERIFY_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\\n")
if message := os.environ.get("STAGED_VERIFY_BLACK_STDERR"):
    print(message, file=sys.stderr)
raise SystemExit(int(os.environ.get("STAGED_VERIFY_BLACK_EXIT", "0")))
""",
        encoding="utf-8",
    )
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(fake_modules), existing_pythonpath) if value
    )

    (repo / ".gitignore").write_text(
        ".test-tools/\n.tool-calls.jsonl\nfrontend/node_modules/\n",
        encoding="utf-8",
    )
    (repo / "README.txt").write_text("baseline\n", encoding="utf-8")
    _checked(
        ["git", "add", ".gitignore", "README.txt", "scripts/verify-staged.ps1"],
        repo,
        environment,
    )
    _checked(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "baseline"],
        repo,
        environment,
    )
    return repo, environment, log_path


def _install_prettier_recorder(
    repo: Path,
    *,
    version: str = "3.6.2",
    bin_entry: str = "./bin/prettier.cjs",
) -> Path:
    package_directory = repo / "frontend" / "node_modules" / "prettier"
    bin_directory = package_directory / "bin"
    bin_directory.mkdir(parents=True, exist_ok=True)
    (package_directory / "package.json").write_text(
        json.dumps(
            {"name": "prettier", "version": version, "bin": bin_entry},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    entry = package_directory / "bin" / "prettier.cjs"
    entry.write_text(
        """const fs = require("fs");
const record = {tool: "prettier", argv: process.argv.slice(2), cwd: process.cwd()};
fs.appendFileSync(
  process.env.STAGED_VERIFY_LOG,
  JSON.stringify(record) + "\\n",
  {encoding: "utf8"},
);
process.exit(Number(process.env.STAGED_VERIFY_PRETTIER_EXIT || "0"));
""",
        encoding="utf-8",
    )
    return entry


def _run(repo: Path, environment: dict[str, str]):
    shell = _powershell()
    command = [shell, "-NoProfile"]
    if Path(shell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", "scripts/verify-staged.ps1"])
    return run_command(command, repo, environment)


def _failure(repo: Path, environment: dict[str, str]) -> str:
    with pytest.raises(AssertionError) as caught:
        _run(repo, environment)
    return str(caught.value)


def _records(log_path: Path) -> list[dict[str, object]]:
    if not log_path.exists():
        return []
    return [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]


def _write(repo: Path, relative_path: str, content: str = "value = 1\n") -> Path:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="")
    return target


def _stage(repo: Path, environment: dict[str, str], *paths: str) -> None:
    _checked(["git", "add", "--", *paths], repo, environment)


def test_empty_index_succeeds_without_starting_formatters(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)

    _run(repo, environment)

    assert _records(log_path) == []


def test_python_files_are_black_checked_together_with_literal_paths(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    paths = ["space name.py", "unicode-路径.py"]
    for path in paths:
        _write(repo, path)
    _stage(repo, environment, *paths)

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert records[0]["tool"] == "black"
    assert records[0]["argv"][:2] == ["--check", "--"]
    assert set(records[0]["argv"][2:]) == set(paths)
    assert Path(str(records[0]["cwd"])) == repo


def test_staged_python_starts_python_exactly_once(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    python_log = _install_python_recorder(repo, environment)
    path = "single-process.py"
    _write(repo, path)
    _stage(repo, environment, path)

    _run(repo, environment)

    calls = [
        json.loads(line) for line in python_log.read_text(encoding="utf-8").splitlines()
    ]
    assert calls == [["-m", "black", "--check", "--", path]]


def test_successful_black_stderr_is_not_reported_as_native_command_error(
    tmp_path: Path,
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    environment["STAGED_VERIFY_BLACK_STDERR"] = "Black success detail"
    path = "success.py"
    _write(repo, path)
    _stage(repo, environment, path)

    result = _run(repo, environment)

    assert "NativeCommandError" not in result.stdout + result.stderr
    assert "Black success detail" in result.stdout + result.stderr


def _install_python_recorder(repo: Path, environment: dict[str, str]) -> Path:
    recorder_directory = repo / ".python-recorder"
    recorder_directory.mkdir()
    log_path = repo / ".python-calls.jsonl"
    (recorder_directory / "sitecustomize.py").write_text(
        """import json
import os
import sys

if sys.orig_argv[1:3] == ["-m", "black"]:
    with open(os.environ["STAGED_VERIFY_PYTHON_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(sys.orig_argv[1:], ensure_ascii=False) + "\\n")
""",
        encoding="utf-8",
    )
    environment["STAGED_VERIFY_PYTHON_LOG"] = str(log_path)
    environment["PYTHONHOME"] = sys.prefix
    environment["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (str(recorder_directory), environment.get("PYTHONPATH"))
        if value
    )
    environment["PATH"] = (
        str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
    )
    return log_path


@pytest.mark.skipif(os.name != "nt", reason="Windows command-wrapper policy")
def test_python_cmd_wrapper_is_rejected_without_execution(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    wrapper_directory = repo / ".python-wrapper"
    wrapper_directory.mkdir()
    marker = repo / "wrapper-executed"
    (wrapper_directory / "python.cmd").write_text(
        "@echo off\r\n"
        'type nul > "%STAGED_VERIFY_WRAPPER_MARKER%"\r\n'
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    environment["STAGED_VERIFY_WRAPPER_MARKER"] = str(marker)
    environment["PATH"] = str(wrapper_directory) + os.pathsep + environment["PATH"]
    path = "wrapper-probe.py"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "python" in failure.casefold()
    assert "native" in failure.casefold() or "executable" in failure.casefold()
    assert not marker.exists()
    assert _records(log_path) == []


def test_native_python_preserves_one_literal_special_filename_without_side_effects(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    python_log = _install_python_recorder(repo, environment)
    path = "; $(New-Item injected) [x] ' unicode-路径.py"
    _write(repo, path)
    _stage(repo, environment, path)

    _run(repo, environment)

    calls = [
        json.loads(line) for line in python_log.read_text(encoding="utf-8").splitlines()
    ]
    assert calls == [["-m", "black", "--check", "--", path]]
    assert _records(log_path)[0]["argv"] == ["--check", "--", path]
    assert not (repo / "injected").exists()


def test_newline_and_glob_like_staged_names_remain_literal(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    paths = ["glob[ab].py"]
    if os.name != "nt":
        paths.append("line\nbreak.py")
    for path in paths:
        _write(repo, path)
    _stage(repo, environment, *paths)

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert set(records[0]["argv"][2:]) == set(paths)


def test_web_and_docs_files_use_one_pinned_prettier_with_frontend_relative_paths(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo)
    paths = ["frontend/src/web file.ts", "docs/guide.md"]
    for path in paths:
        _write(repo, path, "const value = 1;\n")
    _stage(repo, environment, *paths)

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert records[0]["tool"] == "prettier"
    assert records[0]["argv"][:2] == ["--check", "--"]
    assert {str(value).replace("\\", "/") for value in records[0]["argv"][2:]} == {
        "src/web file.ts",
        "../docs/guide.md",
    }
    assert Path(str(records[0]["cwd"])) == repo / "frontend"


def test_every_supported_web_extension_is_sent_to_prettier(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo)
    paths = [f"frontend/src/probe.{extension}" for extension in WEB_EXTENSIONS]
    for path in paths:
        _write(repo, path, "content\n")
    _stage(repo, environment, *paths)

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert records[0]["argv"][:2] == ["--check", "--"]
    assert {str(value).replace("\\", "/") for value in records[0]["argv"][2:]} == {
        f"src/probe.{extension}" for extension in WEB_EXTENSIONS
    }


def test_prettier_batches_option_like_unicode_glob_and_newline_paths_literally(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo)
    paths = ["frontend/--config=foo/probe.ts", "docs/说明[ab].md"]
    if os.name != "nt":
        paths.append("docs/line\nbreak.md")
    for path in paths:
        _write(repo, path, "content\n")
    _stage(repo, environment, *paths)

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert records[0]["tool"] == "prettier"
    assert records[0]["argv"][:2] == ["--check", "--"]
    actual_paths = {str(value).replace("\\", "/") for value in records[0]["argv"][2:]}
    expected_paths = {"--config=foo/probe.ts", "../docs/说明[ab].md"}
    if os.name != "nt":
        expected_paths.add("../docs/line\nbreak.md")
    assert actual_paths == expected_paths


@pytest.mark.parametrize(
    ("tool", "path", "exit_code"),
    [("black", "failure.py", 23), ("prettier", "frontend/failure.ts", 19)],
)
def test_formatter_failures_propagate(
    tmp_path: Path, tool: str, path: str, exit_code: int
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    if tool == "prettier":
        _install_prettier_recorder(repo)
    environment[f"STAGED_VERIFY_{tool.upper()}_EXIT"] = str(exit_code)
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert f"status {exit_code}" in failure
    assert [record["tool"] for record in _records(log_path)] == [tool]
    if tool == "black":
        assert "python -m pip install black" not in failure
        assert "format" in failure.casefold()


def test_missing_pinned_prettier_fails_closed_with_dependency_guidance(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "prettier" in failure.casefold()
    assert "depend" in failure.casefold() or "npm" in failure.casefold()
    assert _records(log_path) == []


def test_prettier_package_version_must_be_exactly_pinned(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo, version="3.6.1")
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "version" in failure.casefold()
    assert "3.6.2" in failure
    assert _records(log_path) == []


def test_prettier_cli_entry_must_stay_inside_its_package(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo, bin_entry="../outside.cjs")
    _write(repo, "frontend/node_modules/outside.cjs", "process.exit(0);\n")
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "package" in failure.casefold()
    assert "within" in failure.casefold() or "inside" in failure.casefold()
    assert _records(log_path) == []


def test_prettier_cli_entry_must_exist_as_a_real_file(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    entry = _install_prettier_recorder(repo)
    entry.unlink()
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "prettier" in failure.casefold()
    assert "CLI entry" in failure
    assert _records(log_path) == []


def test_prettier_cli_entry_rejects_filesystem_links(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    entry = _install_prettier_recorder(repo)
    outside = repo.parent / "outside-prettier.cjs"
    outside.write_text("process.exit(0);\n", encoding="utf-8")
    entry.unlink()
    try:
        entry.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"filesystem does not permit test symbolic links: {error}")
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "symbolic link" in failure.casefold() or "reparse" in failure.casefold()
    assert _records(log_path) == []


def test_missing_node_fails_closed_with_dependency_guidance(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _install_prettier_recorder(repo)
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)
    _restrict_path_to_git(repo, environment)
    assert shutil.which("node", path=environment["PATH"]) is None

    failure = _failure(repo, environment)

    assert "Missing Node.js executable" in failure
    assert "install node.js" in failure.casefold()
    assert _records(log_path) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows command-interpreter regression")
def test_actual_pinned_prettier_preserves_windows_shell_sensitive_literal_path(
    tmp_path: Path,
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    source_package = PROJECT_ROOT / "frontend" / "node_modules" / "prettier"
    assert source_package.is_dir(), "pinned Prettier package must be installed"
    destination_package = repo / "frontend" / "node_modules" / "prettier"
    destination_package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_package, destination_package)
    path = "frontend/docs/shell-%SAFE%!bang!&caret^.md"
    target = _write(repo, path, "# Shell safe\n")
    _stage(repo, environment, path)
    before = target.read_bytes()
    status_before = run_command(
        ["git", "status", "--porcelain=v1", "-z"], repo, environment
    ).stdout

    _run(repo, environment)

    assert target.read_bytes() == before
    assert (
        run_command(["git", "status", "--porcelain=v1", "-z"], repo, environment).stdout
        == status_before
    )
    assert run_command(["git", "diff", "--", path], repo, environment).stdout == ""
    assert run_command(
        ["git", "diff", "--cached", "--name-only", "--", path],
        repo,
        environment,
    ).stdout.splitlines() == [path]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction policy")
def test_registered_worktree_node_modules_junction_is_allowed(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    sibling = tmp_path / "registered-worktree"
    _add_registered_worktree(repo, sibling, environment)
    _write_matching_frontend_manifests(repo, sibling)
    _install_prettier_recorder(sibling)
    _create_junction(
        repo / "frontend" / "node_modules",
        sibling / "frontend" / "node_modules",
        environment,
    )
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    _run(repo, environment)

    assert [record["tool"] for record in _records(log_path)] == ["prettier"]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction policy")
def test_unregistered_node_modules_junction_target_is_rejected(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    target = tmp_path / "unregistered-target"
    _write_matching_frontend_manifests(repo, target)
    _install_prettier_recorder(target)
    _create_junction(
        repo / "frontend" / "node_modules",
        target / "frontend" / "node_modules",
        environment,
    )
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "registered" in failure.casefold()
    assert "worktree" in failure.casefold()
    assert _records(log_path) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction policy")
def test_registered_junction_requires_identical_frontend_manifests(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    sibling = tmp_path / "mismatched-worktree"
    _add_registered_worktree(repo, sibling, environment)
    _write_matching_frontend_manifests(repo, sibling)
    (sibling / "frontend" / "package-lock.json").write_text(
        '{"lockfileVersion":2}\n', encoding="utf-8"
    )
    _install_prettier_recorder(sibling)
    _create_junction(
        repo / "frontend" / "node_modules",
        sibling / "frontend" / "node_modules",
        environment,
    )
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "manifest" in failure.casefold()
    assert "match" in failure.casefold()
    assert _records(log_path) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction policy")
def test_registered_junction_still_rejects_nested_prettier_reparse(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    sibling = tmp_path / "nested-reparse-worktree"
    _add_registered_worktree(repo, sibling, environment)
    _write_matching_frontend_manifests(repo, sibling)
    entry = _install_prettier_recorder(sibling)
    source_bin = entry.parent
    outside_bin = tmp_path / "outside-prettier-bin"
    shutil.copytree(source_bin, outside_bin)
    shutil.rmtree(source_bin)
    _create_junction(source_bin, outside_bin, environment)
    _create_junction(
        repo / "frontend" / "node_modules",
        sibling / "frontend" / "node_modules",
        environment,
    )
    path = "frontend/probe.ts"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "symbolic link" in failure.casefold() or "reparse" in failure.casefold()
    assert _records(log_path) == []


def _add_registered_worktree(
    repo: Path, target: Path, environment: dict[str, str]
) -> None:
    _checked(
        ["git", "worktree", "add", "--detach", str(target), "HEAD"],
        repo,
        environment,
    )


def _write_matching_frontend_manifests(current: Path, target: Path) -> None:
    package_text = '{"name":"frontend","private":true}\n'
    lock_text = '{"lockfileVersion":3}\n'
    for worktree in (current, target):
        frontend = worktree / "frontend"
        frontend.mkdir(parents=True, exist_ok=True)
        (frontend / "package.json").write_text(package_text, encoding="utf-8")
        (frontend / "package-lock.json").write_text(lock_text, encoding="utf-8")


def _create_junction(link: Path, target: Path, environment: dict[str, str]) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    junction_environment = environment.copy()
    junction_environment["STAGED_TEST_JUNCTION_LINK"] = str(link)
    junction_environment["STAGED_TEST_JUNCTION_TARGET"] = str(target)
    command = [
        _powershell(),
        "-NoProfile",
        "-Command",
        "$ErrorActionPreference='Stop'; "
        "New-Item -ItemType Junction -Path "
        "$env:STAGED_TEST_JUNCTION_LINK -Target "
        "$env:STAGED_TEST_JUNCTION_TARGET | Out-Null",
    ]
    try:
        run_command(command, link.parent, junction_environment)
    except AssertionError as error:
        pytest.skip(f"filesystem does not permit test junctions: {error}")


def test_missing_python_fails_closed_with_executable_setup_guidance(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "probe.py"
    _write(repo, path)
    _stage(repo, environment, path)
    _restrict_path_to_git(repo, environment)
    assert shutil.which("python", path=environment["PATH"]) is None

    failure = _failure(repo, environment)

    assert "python" in failure.casefold()
    assert "python -m pip install black" in failure
    assert _records(log_path) == []


def test_missing_black_fails_closed_with_executable_setup_guidance(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    black_module = repo / ".test-tools" / "black"
    (black_module / "__init__.py").write_text(
        "raise ImportError('Black deliberately unavailable')\n", encoding="utf-8"
    )
    (black_module / "__main__.py").unlink()
    path = "probe.py"
    _write(repo, path)
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "black" in failure.casefold()
    assert "python -m pip install black" in failure
    assert _records(log_path) == []


def _restrict_path_to_git(repo: Path, environment: dict[str, str]) -> None:
    real_git = shutil.which("git")
    assert real_git is not None
    if os.name == "nt":
        system_directory = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32"
        path_entries = [str(Path(real_git).parent), str(system_directory)]
    else:
        git_only_directory = repo / ".git-only-path"
        git_only_directory.mkdir()
        git_launcher = git_only_directory / "git"
        git_launcher.symlink_to(real_git)
        path_entries = [str(git_only_directory)]
    environment["PATH"] = os.pathsep.join(path_entries)


def test_cached_diff_check_failure_propagates_before_formatters(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "bad.py"
    _write(repo, path, "value = 1  \n")
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "trailing whitespace" in failure
    assert _records(log_path) == []


def test_unstaged_and_untracked_files_do_not_expand_formatter_scope(
    tmp_path: Path,
) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    _write(repo, "tracked.py")
    _stage(repo, environment, "tracked.py")
    _checked(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "tracked"],
        repo,
        environment,
    )

    staged = "only-staged.py"
    _write(repo, staged)
    _stage(repo, environment, staged)
    _write(repo, "tracked.py", "value = 2\n")
    _write(repo, "untracked.py", "value = 3\n")

    _run(repo, environment)

    records = _records(log_path)
    assert len(records) == 1
    assert records[0]["argv"] == ["--check", "--", staged]


def test_staged_file_with_unstaged_overlay_fails_closed(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "overlay.py"
    _write(repo, path, "value = 0\n")
    _stage(repo, environment, path)
    _checked(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "tracked"],
        repo,
        environment,
    )
    _write(repo, path, "value = 1\n")
    _stage(repo, environment, path)
    _write(repo, path, "value = 2\n")

    failure = _failure(repo, environment)

    assert "unstaged" in failure.casefold()
    assert "stage" in failure.casefold()
    assert _records(log_path) == []


def test_deleted_files_are_excluded(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "deleted.py"
    _write(repo, path)
    _stage(repo, environment, path)
    _checked(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "tracked"],
        repo,
        environment,
    )
    (repo / path).unlink()
    _checked(["git", "add", "-u", "--", path], repo, environment)

    _run(repo, environment)

    assert _records(log_path) == []


def test_missing_staged_worktree_file_fails_closed(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    blob = run_command(
        ["git", "hash-object", "-w", "--stdin"], repo, environment
    ).stdout.strip()
    path = "missing.py"
    _checked(
        ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"],
        repo,
        environment,
    )

    failure = _failure(repo, environment)

    assert "missing" in failure.casefold() or "not found" in failure.casefold()
    assert _records(log_path) == []


def test_git_index_mode_120000_is_rejected(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    path = "index-link.py"
    _write(repo, path, "outside-target")
    blob = run_command(
        ["git", "hash-object", "-w", path], repo, environment
    ).stdout.strip()
    _checked(
        ["git", "update-index", "--add", "--cacheinfo", f"120000,{blob},{path}"],
        repo,
        environment,
    )

    failure = _failure(repo, environment)

    assert "symbolic link" in failure.casefold() or "120000" in failure
    assert _records(log_path) == []


def test_filesystem_symbolic_link_is_rejected(tmp_path: Path) -> None:
    repo, environment, log_path = _prepare_repo(tmp_path)
    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    path = "filesystem-link.py"
    linked = repo / path
    try:
        linked.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"filesystem does not permit test symbolic links: {error}")
    blob = run_command(
        ["git", "hash-object", "-w", "--stdin"], repo, environment
    ).stdout.strip()
    _checked(
        ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"],
        repo,
        environment,
    )

    failure = _failure(repo, environment)

    assert "symbolic link" in failure.casefold() or "reparse" in failure.casefold()
    assert _records(log_path) == []


@pytest.mark.parametrize("malicious_path", ["../outside.py", "/absolute.py"])
def test_enumerated_paths_must_be_repo_relative_without_traversal(
    tmp_path: Path, malicious_path: str
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _install_git_enumerator_shim(
        repo, environment, malicious_path.encode("utf-8") + b"\0"
    )

    failure = _failure(repo, environment)

    assert "relative" in failure.casefold() or "traversal" in failure.casefold()


def test_invalid_utf8_from_git_is_rejected(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _install_git_enumerator_shim(repo, environment, b"invalid-\xff.py\0")

    failure = _failure(repo, environment)

    assert "utf-8" in failure.casefold()


@pytest.mark.parametrize(
    "payload",
    [b"truncated.py", b"valid.py\0truncated.py", b"\0"],
    ids=["missing-final-nul", "truncated-second-path", "empty-path"],
)
def test_malformed_or_truncated_nul_stream_is_rejected(
    tmp_path: Path, payload: bytes
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _install_git_enumerator_shim(repo, environment, payload)

    failure = _failure(repo, environment)

    assert "invalid utf-8 staged path" in failure.casefold()


def _install_git_enumerator_shim(
    repo: Path, environment: dict[str, str], payload: bytes
) -> None:
    global _WINDOWS_GIT_SHIM

    real_git = shutil.which("git")
    assert real_git is not None
    shim_directory = repo / ".git-enumerator-shim"
    shim_directory.mkdir()
    if os.name == "nt":
        launcher = shim_directory / "git.exe"
        if _WINDOWS_GIT_SHIM is not None:
            shutil.copy2(_WINDOWS_GIT_SHIM, launcher)
        else:
            source = shim_directory / "git-shim.cs"
            source.write_text(
                """using System;
using System.IO;

internal static class GitShim
{
    private static int Main(string[] args)
    {
        string[] expected = {
            "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"
        };
        bool isEnumeration = args.Length == expected.Length;
        for (int index = 0; isEnumeration && index < args.Length; index++)
        {
            isEnumeration = String.Equals(args[index], expected[index], StringComparison.Ordinal);
        }
        if (isEnumeration)
        {
            byte[] payload = Convert.FromBase64String(
                Environment.GetEnvironmentVariable("STAGED_VERIFY_GIT_PAYLOAD")
            );
            using (Stream output = Console.OpenStandardOutput())
            {
                output.Write(payload, 0, payload.Length);
            }
        }
        return 0;
    }
}
""",
                encoding="utf-8",
            )
            compiler_candidates = [
                Path(os.environ.get("WINDIR", r"C:\Windows"))
                / "Microsoft.NET"
                / framework
                / "v4.0.30319"
                / "csc.exe"
                for framework in ("Framework64", "Framework")
            ]
            compiler = next(
                (path for path in compiler_candidates if path.is_file()), None
            )
            assert (
                compiler is not None
            ), "Windows .NET Framework C# compiler is required"
            _checked(
                [
                    str(compiler),
                    "/nologo",
                    "/target:exe",
                    f"/out:{launcher}",
                    str(source),
                ],
                repo,
                environment,
            )
            _WINDOWS_GIT_SHIM = launcher
    else:
        shim_script = shim_directory / "git-shim.py"
        shim_script.write_text(
            """import base64
import os
import subprocess
import sys

args = sys.argv[1:]
expected = ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]
if args == expected:
    sys.stdout.buffer.write(base64.b64decode(os.environ["STAGED_VERIFY_GIT_PAYLOAD"]))
    raise SystemExit(0)
raise SystemExit(subprocess.run([os.environ["STAGED_VERIFY_REAL_GIT"], *args]).returncode)
""",
            encoding="utf-8",
        )
        launcher = shim_directory / "git"
        launcher.write_text(
            "#!/bin/sh\n"
            'exec "$STAGED_VERIFY_PYTHON" "$(dirname "$0")/git-shim.py" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    environment["STAGED_VERIFY_REAL_GIT"] = real_git
    environment["STAGED_VERIFY_GIT_PAYLOAD"] = base64.b64encode(payload).decode("ascii")
    environment["PATH"] = str(shim_directory) + os.pathsep + environment["PATH"]


def test_prettier_dependency_is_pinned_exactly() -> None:
    package = json.loads(
        (PROJECT_ROOT / "frontend" / "package.json").read_text("utf-8")
    )
    lock = json.loads(
        (PROJECT_ROOT / "frontend" / "package-lock.json").read_text("utf-8")
    )

    assert package["devDependencies"]["prettier"] == "3.6.2"
    assert lock["packages"][""]["devDependencies"]["prettier"] == "3.6.2"
    assert lock["packages"]["node_modules/prettier"]["version"] == "3.6.2"
