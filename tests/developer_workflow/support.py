"""Isolated process and Git helpers for developer-workflow contract tests."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import NoReturn


def run_command(
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a command with bounded collection and fail with useful diagnostics."""
    popen_options: dict[str, object] = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True

    process = subprocess.Popen(args, **popen_options)  # type: ignore[arg-type]
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _terminate_process_tree(process)
        stdout, stderr = _collect_after_termination(process, error)
        _raise_failure(args, stdout, stderr, f"timed out after {timeout}s")

    if process.returncode:
        _raise_failure(args, stdout, stderr, f"exited with status {process.returncode}")
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def init_repo(path: Path) -> dict[str, str]:
    """Create a Git repository with no user-level Git or pytest configuration."""
    path.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    global_config = path / ".gitconfig-test"
    global_config.touch(exist_ok=True)
    environment["GIT_CONFIG_GLOBAL"] = str(global_config)
    run_command(["git", "init"], path, environment)
    global_config = path / ".git" / "test-global-config"
    (path / ".gitconfig-test").replace(global_config)
    environment["GIT_CONFIG_GLOBAL"] = str(global_config)
    run_command(
        ["git", "config", "user.name", "Developer Workflow Test"], path, environment
    )
    run_command(
        ["git", "config", "user.email", "developer-workflow@example.invalid"],
        path,
        environment,
    )
    return environment


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _collect_after_termination(
    process: subprocess.Popen[str], error: subprocess.TimeoutExpired
) -> tuple[str, str]:
    try:
        return process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired as final_error:
            _raise_failure(
                process.args,
                _as_text(final_error.stdout),
                _as_text(final_error.stderr),
                "could not be collected after termination",
            )


def _raise_failure(
    args: object, stdout: object, stderr: object, reason: str
) -> NoReturn:
    raise AssertionError(
        f"Command {list(args) if isinstance(args, (list, tuple)) else args!r} {reason}. "
        f"stdout={_as_text(stdout)!r}; stderr={_as_text(stderr)!r}"
    )


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
