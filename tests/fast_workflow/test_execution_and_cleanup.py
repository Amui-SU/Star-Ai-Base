import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from . import support
from .support import (
    VerifierRepo,
    run_checked,
    read,
    run_subprocess_with_timeout,
    run_verifier,
    terminate_process_tree,
    write_frontend_stub,
    write_frontend_target,
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


def test_timeout_diagnostics_remain_bounded_when_a_descendant_keeps_pipes_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    command = ["verifier", "--probe"]
    communicate_timeouts: list[float] = []

    class FakeProcess:
        pid = 1234
        returncode = -9

        def communicate(self, timeout):
            communicate_timeouts.append(timeout)
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output=b"parent-started",
                stderr=b"descendant-pipe-open",
            )

        def poll(self):
            return None

        def kill(self):
            pass

        def wait(self, timeout):
            pass

    def fail_taskkill(*args, **kwargs):
        raise OSError("taskkill unavailable")

    monkeypatch.setattr(support.os, "name", "nt")
    monkeypatch.setattr(
        support.subprocess, "Popen", lambda *args, **kwargs: FakeProcess()
    )
    monkeypatch.setattr(support.subprocess, "run", fail_taskkill)

    with pytest.raises(AssertionError) as error:
        run_subprocess_with_timeout(
            command,
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout_seconds=0.1,
        )

    diagnostic = str(error.value)
    assert communicate_timeouts == [0.1, 5]
    assert repr(command) in diagnostic
    assert "parent-started" in diagnostic
    assert "descendant-pipe-open" in diagnostic
    assert "stdout=" in diagnostic
    assert "stderr=" in diagnostic


def test_subprocess_timeout_cleanup_has_no_unbounded_pipe_waits():
    support_source = read("tests/fast_workflow/support.py")

    assert re.search(r"\.communicate\(\s*\)", support_source) is None
    assert re.search(r"\.wait\(\s*\)", support_source) is None


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


def test_frontend_executable_resolution_does_not_depend_on_os_environment(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    environment.pop("OS", None)
    write_frontend_target(repo, "src/widget.ts")
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-LintFile", "src/widget.ts")

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == ["--", "src/widget.ts"]


def test_lint_bracket_path_is_rejected_before_eslint_can_match_a_sibling(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    write_frontend_target(repo, "src/Case.ts")
    run_checked(["git", "add", "frontend/src/Case.ts"], repo, environment)
    run_checked(
        ["git", "commit", "--no-gpg-sign", "--no-verify", "-m", "add sibling"],
        repo,
        environment,
    )
    write_frontend_target(repo, "src/[C]ase.ts")
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-LintFile", "src/[C]ase.ts")

    assert result.returncode != 0
    assert "ESLint glob" in result.stdout + result.stderr
    assert not log.exists()


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
