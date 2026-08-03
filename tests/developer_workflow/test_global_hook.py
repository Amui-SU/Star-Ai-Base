"""Contract tests for the no-network global pre-commit dispatcher."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = PROJECT_ROOT / "scripts" / "git-hooks" / "pre-commit"


def _git_bash() -> str:
    git = Path(shutil.which("git") or "")
    candidates = [
        git.parent.parent / "bin" / "bash.exe",
        git.parent.parent / "usr" / "bin" / "bash.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    bash = shutil.which("bash")
    if bash:
        return bash
    pytest.skip("Git Bash or a Unix bash is required")


def _prepare_repo(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    repo = tmp_path / "repo"
    environment = init_repo(repo)
    hook = repo / "pre-commit"
    shutil.copy2(HOOK_SOURCE, hook)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    tools = repo / ".hook-test-tools"
    tools.mkdir()
    log = repo / "hook-argv.bin"
    environment["HOOK_TEST_LOG"] = str(log)
    environment["HOOK_TEST_EXIT"] = "0"
    real_git = Path(shutil.which("git") or "")
    git_root = real_git.parent.parent
    environment["PATH"] = os.pathsep.join(
        [str(tools), str(real_git.parent), str(git_root / "usr" / "bin")]
    )
    return repo, environment, log


def _write(repo: Path, path: str, content: str = "value = 1\n") -> Path:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _stage(repo: Path, environment: dict[str, str], *paths: str) -> None:
    run_command(["git", "add", "--", *paths], repo, environment)


def _tool(repo: Path, name: str, *, exit_code: str = "${HOOK_TEST_EXIT:-0}") -> None:
    target = repo / ".hook-test-tools" / name
    target.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\0\' CALL {name!r} "$#" "$@" >> "$HOOK_TEST_LOG"\n'
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    target.chmod(target.stat().st_mode | stat.S_IXUSR)


def _records(log: Path) -> list[tuple[str, list[str]]]:
    if not log.exists():
        return []
    fields = log.read_bytes().decode("utf-8").split("\0")
    assert fields.pop() == ""
    records: list[tuple[str, list[str]]] = []
    while fields:
        assert fields.pop(0) == "CALL"
        tool = fields.pop(0)
        count = int(fields.pop(0))
        records.append((tool, fields[:count]))
        del fields[:count]
    return records


def _run(repo: Path, environment: dict[str, str]) -> str:
    return run_command(
        [_git_bash(), str(repo / "pre-commit")], repo, environment
    ).stderr


def _failure(repo: Path, environment: dict[str, str]) -> str:
    with pytest.raises(AssertionError) as failure:
        _run(repo, environment)
    return str(failure.value)


def _configure_local(repo: Path, environment: dict[str, str], value: str) -> None:
    run_command(
        ["git", "config", "--local", "workflow.useRepositoryHook", value],
        repo,
        environment,
    )


def _add_repository_verifier(repo: Path) -> Path:
    verifier = repo / "scripts" / "verify-staged.ps1"
    verifier.parent.mkdir(parents=True, exist_ok=True)
    verifier.write_text("# fixed repository verifier\n", encoding="utf-8")
    return verifier


def test_exact_local_true_dispatches_to_fixed_repository_verifier(
    tmp_path: Path,
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    verifier = _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    _configure_local(repo, environment, "true")

    _run(repo, environment)

    assert _records(log) == [
        (
            "pwsh",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", verifier.as_posix()],
        )
    ]


@pytest.mark.parametrize("value", ["false", "yes", "1", "TRUE", "true "])
def test_noncanonical_local_values_do_not_dispatch(tmp_path: Path, value: str) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    _configure_local(repo, environment, value)

    _run(repo, environment)

    assert _records(log) == []


def test_global_true_does_not_override_missing_local_opt_in(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    run_command(
        ["git", "config", "--global", "workflow.useRepositoryHook", "true"],
        repo,
        environment,
    )

    _run(repo, environment)

    assert _records(log) == []


def test_config_value_is_data_and_never_executed(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    marker = repo / "must-not-exist"
    _configure_local(repo, environment, f"touch {marker}")

    _run(repo, environment)

    assert not marker.exists()
    assert _records(log) == []


@pytest.mark.parametrize("missing", ["script", "powershell"])
def test_enabled_repository_dispatch_fails_closed_when_prerequisite_missing(
    tmp_path: Path, missing: str
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _configure_local(repo, environment, "true")
    if missing != "script":
        _add_repository_verifier(repo)
    if missing != "powershell":
        _tool(repo, "pwsh")

    failure = _failure(repo, environment)

    assert missing in failure.casefold()
    assert _records(log) == []


def test_repository_verifier_failure_propagates(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _add_repository_verifier(repo)
    _tool(repo, "pwsh", exit_code="23")
    _configure_local(repo, environment, "true")

    failure = _failure(repo, environment)

    assert "status 23" in failure


def test_empty_index_is_a_fast_noop(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    for tool in ("ruff", "black", "python", "prettier"):
        _tool(repo, tool)

    _run(repo, environment)

    assert _records(log) == []


def test_literal_paths_are_batched_once_per_language(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _tool(repo, "ruff")
    _tool(repo, "prettier")
    python_paths = ["plain.py", "space name.py", "glob[abc].py"]
    web_paths = ["frontend/\u96ea.ts", "--config.js"]
    for path in python_paths + web_paths:
        _write(
            repo,
            path,
            "const value = 1\n" if not path.endswith(".py") else "value = 1\n",
        )
    _stage(repo, environment, *(python_paths + web_paths))

    _run(repo, environment)

    assert _records(log) == [
        ("ruff", ["format", "--check", "--", *sorted(python_paths)]),
        ("prettier", ["--check", "--", *sorted(web_paths)]),
    ]


@pytest.mark.skipif(
    os.name == "nt", reason="Windows forbids newline characters in paths"
)
def test_newline_path_is_passed_as_one_literal_argument(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _tool(repo, "ruff")
    path = "line\nbreak.py"
    _write(repo, path)
    _stage(repo, environment, path)

    _run(repo, environment)

    assert _records(log) == [("ruff", ["format", "--check", "--", path])]


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (
            ("ruff", "black", "python"),
            ("ruff", ["format", "--check", "--", "a.py", "b.py"]),
        ),
        (("black", "python"), ("black", ["--check", "--", "a.py", "b.py"])),
        (("python",), ("python", ["-m", "py_compile", "--", "a.py", "b.py"])),
    ],
)
def test_python_tool_priority_and_batching(
    tmp_path: Path, available: tuple[str, ...], expected: tuple[str, list[str]]
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    for tool in available:
        _tool(repo, tool)
    for path in ("a.py", "b.py"):
        _write(repo, path)
    _stage(repo, environment, "a.py", "b.py")

    _run(repo, environment)

    assert _records(log) == [expected]


def test_missing_optional_tools_warn_without_network_access(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    for forbidden in ("npx", "npm", "curl", "wget", "pip"):
        _tool(repo, forbidden, exit_code="97")
    _write(repo, "probe.py")
    _write(repo, "probe.ts", "const value = 1\n")
    _stage(repo, environment, "probe.py", "probe.ts")

    stderr = _run(repo, environment)

    assert "warning" in stderr.casefold()
    assert "python" in stderr.casefold()
    assert "prettier" in stderr.casefold()
    assert _records(log) == []


@pytest.mark.parametrize("tool", ["ruff", "black", "python", "prettier"])
def test_tool_failure_is_propagated(tmp_path: Path, tool: str) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    _tool(repo, tool, exit_code="29")
    path = "probe.ts" if tool == "prettier" else "probe.py"
    _write(repo, path, "const value = 1\n" if tool == "prettier" else "value = 1\n")
    _stage(repo, environment, path)

    failure = _failure(repo, environment)

    assert "status 29" in failure


def test_acmr_files_are_selected_and_deletions_are_excluded(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _tool(repo, "ruff")
    for path in ("modified.py", "deleted.py", "old.py"):
        _write(repo, path)
    _stage(repo, environment, "modified.py", "deleted.py", "old.py")
    run_command(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "base"],
        repo,
        environment,
    )
    _write(repo, "added.py")
    _write(repo, "modified.py", "value = 2\n")
    (repo / "deleted.py").unlink()
    run_command(["git", "mv", "--", "old.py", "renamed.py"], repo, environment)
    _stage(repo, environment, "added.py", "modified.py", "deleted.py")

    _run(repo, environment)

    assert _records(log) == [
        ("ruff", ["format", "--check", "--", "added.py", "modified.py", "renamed.py"])
    ]


def test_git_enumeration_failure_is_propagated_before_tools(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _tool(repo, "ruff")
    _write(repo, "probe.py")
    _stage(repo, environment, "probe.py")
    (repo / ".git" / "index").write_bytes(b"not a git index")

    failure = _failure(repo, environment)

    assert "index" in failure.casefold()
    assert _records(log) == []


def test_hook_source_contains_no_network_or_command_reinterpretation_escape_hatches() -> (
    None
):
    source = HOOK_SOURCE.read_text(encoding="utf-8").casefold()
    forbidden = (
        "npx",
        "npm exec",
        "--yes",
        "eval",
        "curl",
        "wget",
        "pip install",
        "npm install",
    )

    assert not [token for token in forbidden if token in source]
