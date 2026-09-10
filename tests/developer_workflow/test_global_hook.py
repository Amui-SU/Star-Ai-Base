"""Contract tests for the no-network global pre-commit dispatcher."""

from __future__ import annotations

import os
import shutil
import stat
import sys
import time
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = PROJECT_ROOT / "scripts" / "git-hooks" / "pre-commit"
_WINDOWS_GIT_SHIM: Path | None = None
_PYTHON_FALLBACK = "python" if os.name == "nt" else "python3"


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


def _signaling_tool(repo: Path, name: str, signal_name: str) -> None:
    target = repo / ".hook-test-tools" / name
    target.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\0\' CALL {name!r} "$#" "$@" >> "$HOOK_TEST_LOG"\n'
        f'kill -{signal_name} "$PPID"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    target.chmod(target.stat().st_mode | stat.S_IXUSR)


def _install_git_stream_shim(
    repo: Path, environment: dict[str, str], mode: str
) -> None:
    global _WINDOWS_GIT_SHIM

    real_git = shutil.which("git")
    assert real_git
    shim_directory = repo / ".hook-git-shim"
    shim_directory.mkdir()
    environment["HOOK_TEST_REAL_GIT"] = real_git
    environment["HOOK_TEST_GIT_MODE"] = mode
    if os.name == "nt":
        launcher = shim_directory / "git.exe"
        if _WINDOWS_GIT_SHIM is not None:
            shutil.copy2(_WINDOWS_GIT_SHIM, launcher)
        else:
            source = shim_directory / "git-shim.cs"
            source.write_text(
                """using System;
using System.Diagnostics;
using System.IO;
using System.Text;

internal static class GitShim
{
    private static bool Matches(string[] args, string[] expected)
    {
        if (args.Length != expected.Length) return false;
        for (int index = 0; index < args.Length; index++)
            if (!String.Equals(args[index], expected[index], StringComparison.Ordinal)) return false;
        return true;
    }

    private static int Main(string[] args)
    {
        string mode = Environment.GetEnvironmentVariable("HOOK_TEST_GIT_MODE");
        bool config = Matches(args, new [] { "config", "--local", "--null", "--get-all", "workflow.useRepositoryHook" });
        bool staged = Matches(args, new [] { "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR" });
        if (mode == "config-truncated" && config)
        {
            byte[] payload = Encoding.UTF8.GetBytes("true");
            Console.OpenStandardOutput().Write(payload, 0, payload.Length);
            return 0;
        }
        if (mode == "staged-truncated" && staged)
        {
            byte[] payload = Encoding.UTF8.GetBytes("probe.py");
            Console.OpenStandardOutput().Write(payload, 0, payload.Length);
            return 0;
        }
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = Environment.GetEnvironmentVariable("HOOK_TEST_REAL_GIT");
        info.Arguments = String.Join(" ", args);
        info.UseShellExecute = false;
        Process process = Process.Start(info);
        process.WaitForExit();
        return process.ExitCode;
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
            assert compiler, "Windows .NET Framework C# compiler is required"
            run_command(
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
        script = shim_directory / "git-shim.py"
        script.write_text(
            """import os
import subprocess
import sys

args = sys.argv[1:]
config = ["config", "--local", "--null", "--get-all", "workflow.useRepositoryHook"]
staged = ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]
mode = os.environ["HOOK_TEST_GIT_MODE"]
if mode == "config-truncated" and args == config:
    sys.stdout.buffer.write(b"true")
    raise SystemExit(0)
if mode == "staged-truncated" and args == staged:
    sys.stdout.buffer.write(b"probe.py")
    raise SystemExit(0)
raise SystemExit(subprocess.run([os.environ["HOOK_TEST_REAL_GIT"], *args]).returncode)
""",
            encoding="utf-8",
        )
        launcher = shim_directory / "git"
        launcher.write_text(
            '#!/bin/sh\nexec "$HOOK_TEST_PYTHON" "$(dirname "$0")/git-shim.py" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
        environment["HOOK_TEST_PYTHON"] = sys.executable
    bash_environment = shim_directory / "bash-env.sh"
    bash_environment.write_text(
        "unset -f git 2>/dev/null || true\n"
        'shim_dir=$(cygpath -u "$HOOK_TEST_SHIM_DIR" 2>/dev/null || printf %s "$HOOK_TEST_SHIM_DIR")\n'
        'PATH="$shim_dir:$PATH"\n'
        "export PATH\n",
        encoding="utf-8",
    )
    environment["HOOK_TEST_SHIM_DIR"] = str(shim_directory)
    environment["BASH_ENV"] = bash_environment.as_posix()


def _install_hanging_git_shim(
    repo: Path, environment: dict[str, str], phase: str
) -> Path:
    real_git = shutil.which("git")
    assert real_git
    shim_directory = repo / ".hook-hang-shim"
    shim_directory.mkdir()
    marker = repo / "producer-ready"
    pid_file = repo / "producer-pid"
    launcher = shim_directory / "git"
    launcher.write_text(
        "#!/bin/bash\n"
        'is_config=0; [ "$1" = config ] && is_config=1\n'
        'is_staged=0; [ "$1" = diff ] && is_staged=1\n'
        'if { [ "$HOOK_TEST_HANG_PHASE" = config ] && [ "$is_config" -eq 1 ]; } || '
        '{ [ "$HOOK_TEST_HANG_PHASE" = staged ] && [ "$is_staged" -eq 1 ]; }; then\n'
        "  trap '' TERM\n"
        '  printf %s "$$" > "$HOOK_TEST_PRODUCER_PID"\n'
        '  printf ready > "$HOOK_TEST_PRODUCER_READY"\n'
        "  while :; do sleep 1; done\n"
        "fi\n"
        'exec "$HOOK_TEST_REAL_GIT" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    bash_environment = shim_directory / "bash-env.sh"
    bash_environment.write_text(
        "unset -f git 2>/dev/null || true\n"
        'shim_dir=$(cygpath -u "$HOOK_TEST_SHIM_DIR" 2>/dev/null || printf %s "$HOOK_TEST_SHIM_DIR")\n'
        'PATH="$shim_dir:$PATH"\n'
        "export PATH\n",
        encoding="utf-8",
    )
    environment["HOOK_TEST_REAL_GIT"] = real_git
    environment["HOOK_TEST_HANG_PHASE"] = phase
    environment["HOOK_TEST_PRODUCER_READY"] = str(marker)
    environment["HOOK_TEST_PRODUCER_PID"] = str(pid_file)
    environment["HOOK_TEST_SHIM_DIR"] = str(shim_directory)
    environment["BASH_ENV"] = bash_environment.as_posix()
    return marker


def _signaled_hook_command(repo: Path, marker: Path, signal_name: str) -> list[str]:
    hook = repo / "pre-commit"
    wrapper = (
        '(trap - HUP INT TERM; exec "$1") & hook_pid=$!; '
        '(while [ ! -s "$2" ]; do sleep 0.02; done; kill -"$3" "$hook_pid") & '
        'wait "$hook_pid"; hook_status=$?; '
        'producer_pid=$(cat "$4"); '
        'if kill -0 "$producer_pid" 2>/dev/null; then '
        'kill -KILL "$producer_pid" 2>/dev/null || true; exit 99; fi; '
        'exit "$hook_status"'
    )
    return [
        _git_bash(),
        "-c",
        wrapper,
        "signal-fixture",
        hook.as_posix(),
        marker.as_posix(),
        signal_name,
        (repo / "producer-pid").as_posix(),
    ]


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


def _collision_command(repo: Path, kind: str) -> list[str]:
    hooks = repo / ".git" / "hooks"
    hook = repo / "pre-commit"
    wrapper = (
        'buffer="$1/.global-pre-commit-$2.$$"; '
        'printf %s preserved > "$buffer"; '
        'exec "$3"'
    )
    return [
        _git_bash(),
        "-c",
        wrapper,
        "collision-fixture",
        hooks.as_posix(),
        kind,
        hook.as_posix(),
    ]


def _assert_collision_preserved(repo: Path, kind: str) -> None:
    matches = list((repo / ".git" / "hooks").glob(f".global-pre-commit-{kind}.*"))
    assert len(matches) == 1
    assert matches[0].read_text(encoding="utf-8") == "preserved"


def _configure_local(repo: Path, environment: dict[str, str], value: str) -> None:
    run_command(
        ["git", "config", "--local", "workflow.useRepositoryHook", value],
        repo,
        environment,
    )


def _add_local(repo: Path, environment: dict[str, str], value: str) -> None:
    run_command(
        ["git", "config", "--local", "--add", "workflow.useRepositoryHook", value],
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


def test_enabled_dispatch_prefers_native_powershell_exe_over_pwsh(
    tmp_path: Path,
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    verifier = _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    _tool(repo, "powershell.exe")
    _configure_local(repo, environment, "true")

    _run(repo, environment)

    assert _records(log) == [
        (
            "powershell.exe",
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


def test_local_true_with_trailing_newline_does_not_dispatch(tmp_path: Path) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    _configure_local(repo, environment, "true\n")

    _run(repo, environment)

    assert _records(log) == []


@pytest.mark.parametrize("values", [("false", "true"), ("true", "true")])
def test_multiple_local_values_never_dispatch(
    tmp_path: Path, values: tuple[str, str]
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    for value in values:
        _add_local(repo, environment, value)

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


@pytest.mark.parametrize(
    "missing",
    [
        "script",
        pytest.param(
            "powershell",
            marks=pytest.mark.skipif(
                os.name != "nt",
                reason="POSIX test PATH retains the system PowerShell Core executable",
            ),
        ),
    ],
)
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


def test_preexisting_staged_buffer_is_ignored_and_preserved(
    tmp_path: Path,
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)

    run_command(_collision_command(repo, "staged"), repo, environment)

    _assert_collision_preserved(repo, "staged")


def test_repository_dispatch_does_not_touch_preexisting_staged_buffer(
    tmp_path: Path,
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    verifier = _add_repository_verifier(repo)
    _tool(repo, "pwsh")
    _configure_local(repo, environment, "true")

    run_command(_collision_command(repo, "staged"), repo, environment)

    _assert_collision_preserved(repo, "staged")
    assert _records(log) == [
        (
            "pwsh",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", verifier.as_posix()],
        )
    ]


def test_preexisting_config_buffer_is_ignored_and_preserved(
    tmp_path: Path,
) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)

    run_command(_collision_command(repo, "config"), repo, environment)

    _assert_collision_preserved(repo, "config")


@pytest.mark.parametrize(
    ("signal_name", "status"), [("HUP", 129), ("INT", 130), ("TERM", 143)]
)
def test_signal_exits_nonzero_without_running_later_formatter(
    tmp_path: Path, signal_name: str, status: int
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _signaling_tool(repo, "ruff", signal_name)
    _tool(repo, "prettier")
    _write(repo, "probe.py")
    _write(repo, "probe.ts", "const value = 1\n")
    _stage(repo, environment, "probe.py", "probe.ts")

    failure = _failure(repo, environment)

    assert f"status {status}" in failure
    assert [tool for tool, _ in _records(log)] == ["ruff"]


@pytest.mark.parametrize("phase", ["config", "staged"])
@pytest.mark.parametrize(
    ("signal_name", "status"), [("HUP", 129), ("INT", 130), ("TERM", 143)]
)
def test_signal_boundedly_reaps_term_ignoring_active_producer(
    tmp_path: Path, phase: str, signal_name: str, status: int
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    marker = _install_hanging_git_shim(repo, environment, phase)
    _tool(repo, "ruff")
    _tool(repo, "prettier")
    _write(repo, "probe.py")
    _write(repo, "probe.ts", "const value = 1\n")
    _stage(repo, environment, "probe.py", "probe.ts")

    started = time.monotonic()
    with pytest.raises(AssertionError) as failure:
        run_command(
            _signaled_hook_command(repo, marker, signal_name),
            repo,
            environment,
            timeout=4,
        )

    assert time.monotonic() - started < 4
    assert f"status {status}" in str(failure.value)
    assert _records(log) == []


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("config-truncated", "local config"),
        ("staged-truncated", "staged path"),
    ],
)
def test_truncated_nul_stream_fails_closed(
    tmp_path: Path, mode: str, message: str
) -> None:
    repo, environment, log = _prepare_repo(tmp_path)
    _install_git_stream_shim(repo, environment, mode)
    _tool(repo, "ruff")
    selected_git = run_command(
        [_git_bash(), "-c", "type -P git"], repo, environment
    ).stdout
    assert ".hook-git-shim" in selected_git

    failure = _failure(repo, environment)

    assert "truncated" in failure.casefold()
    assert message in failure.casefold()
    assert _records(log) == []


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
        (
            (_PYTHON_FALLBACK,),
            (_PYTHON_FALLBACK, ["-m", "py_compile", "--", "a.py", "b.py"]),
        ),
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
    if os.name == "nt":
        assert "python" in stderr.casefold()
    assert "prettier" in stderr.casefold()
    assert _records(log) == []


@pytest.mark.parametrize("tool", ["ruff", "black", _PYTHON_FALLBACK, "prettier"])
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
