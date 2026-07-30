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


def _install_prettier_recorder(repo: Path) -> Path:
    bin_directory = repo / "frontend" / "node_modules" / ".bin"
    bin_directory.mkdir(parents=True, exist_ok=True)
    recorder = bin_directory / "prettier-recorder.py"
    recorder.write_text(
        """import json
import os
import sys

record = {"tool": "prettier", "argv": sys.argv[1:], "cwd": os.getcwd()}
with open(os.environ["STAGED_VERIFY_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\\n")
raise SystemExit(int(os.environ.get("STAGED_VERIFY_PRETTIER_EXIT", "0")))
""",
        encoding="utf-8",
    )

    if os.name == "nt":
        executable = bin_directory / "prettier.cmd"
        executable.write_text(
            "@echo off\r\n"
            '"%STAGED_VERIFY_PYTHON%" "%~dp0prettier-recorder.py" %*\r\n'
            "exit /b %errorlevel%\r\n",
            encoding="utf-8",
        )
    else:
        executable = bin_directory / "prettier"
        executable.write_text(
            "#!/bin/sh\n"
            'exec "$STAGED_VERIFY_PYTHON" "$(dirname "$0")/prettier-recorder.py" "$@"\n',
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _run(repo: Path, environment: dict[str, str]) -> None:
    shell = _powershell()
    command = [shell, "-NoProfile"]
    if Path(shell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", "scripts/verify-staged.ps1"])
    run_command(command, repo, environment)


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
    assert records[0]["argv"][0] == "--check"
    assert {str(value).replace("\\", "/") for value in records[0]["argv"][1:]} == {
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
    assert {str(value).replace("\\", "/") for value in records[0]["argv"][1:]} == {
        f"src/probe.{extension}" for extension in WEB_EXTENSIONS
    }


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


@pytest.mark.skipif(
    os.name == "nt",
    reason="ProcessStartInfo resolves git.exe before a test git.cmd shim",
)
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


@pytest.mark.skipif(os.name == "nt", reason="Windows Git paths are Unicode strings")
def test_invalid_utf8_from_git_is_rejected(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _install_git_enumerator_shim(repo, environment, b"invalid-\xff.py\0")

    failure = _failure(repo, environment)

    assert "utf-8" in failure.casefold()


def _install_git_enumerator_shim(
    repo: Path, environment: dict[str, str], payload: bytes
) -> None:
    real_git = shutil.which("git")
    assert real_git is not None
    shim_directory = repo / ".git-enumerator-shim"
    shim_directory.mkdir()
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
    if os.name == "nt":
        launcher = shim_directory / "git.cmd"
        launcher.write_text(
            "@echo off\r\n"
            '"%STAGED_VERIFY_PYTHON%" "%~dp0git-shim.py" %*\r\n'
            "exit /b %errorlevel%\r\n",
            encoding="utf-8",
        )
    else:
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
