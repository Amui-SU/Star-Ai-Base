from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

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


def test_init_repo_isolates_git_and_pytest_configuration(tmp_path: Path) -> None:
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


def _process_exists(pid: int) -> bool:
    if os.name != "nt":
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
