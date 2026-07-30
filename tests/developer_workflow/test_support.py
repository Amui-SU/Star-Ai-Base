from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.developer_workflow import support
from tests.developer_workflow.support import init_repo, run_command


def test_run_command_supports_unicode_repository_paths_and_output(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "仓库 含空格"
    environment = init_repo(repository)

    result = run_command(
        [sys.executable, "-X", "utf8", "-c", "print('你好，开发流程')"],
        cwd=repository,
        env=environment,
    )

    assert result.stdout == "你好，开发流程\n"
    assert (
        run_command(["git", "status", "--porcelain"], repository, environment).stdout
        == ""
    )


def test_init_repo_isolates_git_and_pytest_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hostile_global_config = tmp_path / "hostile.gitconfig"
    hostile_global_config.write_text("[user]\nname = Hostile User\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile_global_config))
    monkeypatch.setenv("PYTEST_ADDOPTS", "--tb=short")
    monkeypatch.setenv("PYTEST_PLUGINS", "hostile_plugin")
    environment = init_repo(tmp_path / "isolated repo")

    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert Path(environment["GIT_CONFIG_GLOBAL"]).is_file()
    assert "PYTEST_ADDOPTS" not in environment
    assert "PYTEST_PLUGINS" not in environment
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert (
        run_command(
            ["git", "config", "user.name"], tmp_path / "isolated repo", environment
        ).stdout.strip()
        == "Developer Workflow Test"
    )
    assert (
        run_command(
            ["git", "config", "user.email"], tmp_path / "isolated repo", environment
        ).stdout.strip()
        == "developer-workflow@example.invalid"
    )
    with pytest.raises(AssertionError):
        run_command(
            ["git", "config", "--global", "user.name"],
            tmp_path / "isolated repo",
            environment,
        )


def test_run_command_times_out_and_cleans_up_child_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "child-pid.txt"
    script = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        f"pathlib.Path({str(marker)!r}).write_text(str(child.pid), encoding='utf-8'); "
        "time.sleep(30)"
    )

    started = time.monotonic()
    with pytest.raises(AssertionError, match="timed out") as exc_info:
        run_command(
            [sys.executable, "-c", script], tmp_path, os.environ.copy(), timeout=2
        )
    assert time.monotonic() - started < 15
    assert "stdout=" in str(exc_info.value)
    assert "stderr=" in str(exc_info.value)

    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert marker.exists()
    child_pid = int(marker.read_text(encoding="utf-8"))
    while _process_exists(child_pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _process_exists(child_pid)


def test_run_command_owns_child_when_parent_exits_before_timeout(
    tmp_path: Path,
) -> None:
    child_pid_file = tmp_path / "escaped-child-pid.txt"
    delayed_marker = tmp_path / "escaped-child-marker.txt"
    child_script = (
        "import pathlib, time; "
        "time.sleep(3); "
        f"pathlib.Path({str(delayed_marker)!r}).write_text('alive', encoding='utf-8')"
    )
    parent_script = (
        "import pathlib, subprocess, sys; "
        f"child = subprocess.Popen([sys.executable, '-c', {child_script!r}]); "
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8'); "
        "print(child.pid, flush=True)"
    )

    try:
        with pytest.raises(AssertionError, match="timed out") as exc_info:
            run_command(
                [sys.executable, "-c", parent_script],
                tmp_path,
                os.environ.copy(),
                timeout=1,
            )
        assert Path(sys.executable).name in str(exc_info.value)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            assert not delayed_marker.exists()
            time.sleep(0.2)
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        if os.name == "nt":
            assert not _process_exists(child_pid)
    finally:
        if child_pid_file.exists():
            _force_cleanup(int(child_pid_file.read_text(encoding="utf-8")))


def test_run_command_reports_nonzero_exit_status(tmp_path: Path) -> None:
    with pytest.raises(AssertionError) as exc_info:
        run_command(
            [sys.executable, "-c", "import sys; print('bad output'); sys.exit(7)"],
            tmp_path,
            os.environ.copy(),
        )

    message = str(exc_info.value)
    assert "exited with status 7" in message
    assert Path(sys.executable).name in message
    assert "bad output" in message
    assert "stdout=" in message
    assert "stderr=" in message


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group contract")
def test_run_command_reaps_detached_stdio_child_after_success(tmp_path: Path) -> None:
    child_pid_file = tmp_path / "posix-child-pid.txt"
    delayed_marker = tmp_path / "posix-child-marker.txt"
    child_script = (
        "import pathlib, time; "
        "time.sleep(3); "
        f"pathlib.Path({str(delayed_marker)!r}).write_text('alive', encoding='utf-8')"
    )
    parent_script = (
        "import pathlib, subprocess, sys; "
        f"child = subprocess.Popen([sys.executable, '-c', {child_script!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL); "
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8')"
    )

    try:
        result = run_command(
            [sys.executable, "-c", parent_script],
            tmp_path,
            os.environ.copy(),
            timeout=1,
        )
        assert result.returncode == 0
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            assert not delayed_marker.exists()
            time.sleep(0.2)
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        assert not _process_exists(child_pid)
    finally:
        if child_pid_file.exists():
            _force_cleanup(int(child_pid_file.read_text(encoding="utf-8")))


def test_posix_group_cleanup_kills_stable_group_before_reaping_leader() -> None:
    events: list[tuple[object, ...]] = []

    class FakeProcess:
        pid = 43210

        def wait(self, timeout: float) -> int:
            events.append(("wait", timeout))
            return -9

    def kill_group(process_group: int, requested_signal: int) -> None:
        events.append(("killpg", process_group, requested_signal))

    error = support._kill_posix_group_then_reap(
        FakeProcess(), current_group=12345, kill_group=kill_group, kill_signal=9
    )

    assert error is None
    assert events == [
        ("killpg", 43210, 9),
        ("wait", 10),
    ]


def _process_exists(pid: int) -> bool:
    if os.name != "nt":
        proc_root = Path("/proc")
        if proc_root.is_dir():
            proc_stat = proc_root / str(pid) / "stat"
            try:
                stat_text = proc_stat.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                return False
            _, separator, suffix = stat_text.rpartition(")")
            if separator:
                state_fields = suffix.split()
                if state_fields and state_fields[0] == "Z":
                    return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    return str(pid) in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object contract")
def test_run_command_does_not_start_target_before_job_assignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assignment_complete = tmp_path / "assignment-complete.txt"
    target_started = tmp_path / "target-started.txt"

    class GateProbeJob:
        def __init__(self, process: subprocess.Popen[str]) -> None:
            time.sleep(0.3)
            assert not target_started.exists(), "target started before Job assignment"
            assignment_complete.write_text("ready", encoding="utf-8")

        def close(self) -> None:
            pass

    monkeypatch.setattr(support, "_WindowsJob", GateProbeJob)
    target_script = (
        "import pathlib, sys; "
        f"started = pathlib.Path({str(target_started)!r}); started.write_text('started'); "
        f"assert pathlib.Path({str(assignment_complete)!r}).exists(); print('released')"
    )

    result = run_command(
        [sys.executable, "-c", target_script], tmp_path, os.environ.copy()
    )

    assert result.stdout == "released\n"


def _force_cleanup(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        return
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
