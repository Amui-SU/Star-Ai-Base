"""Isolated process and Git helpers for developer-workflow contract tests."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

_WINDOWS_LAUNCHER = """import json
import subprocess
import sys

payload = sys.stdin.readline()
if not payload:
    raise SystemExit(125)
raise SystemExit(subprocess.run(json.loads(payload), check=False).returncode)
"""

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL

    class _JobBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time_limit", ctypes.c_longlong),
            ("per_job_user_time_limit", ctypes.c_longlong),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_operation_count",
                "write_operation_count",
                "other_operation_count",
                "read_transfer_count",
                "write_transfer_count",
                "other_transfer_count",
            )
        ]

    class _JobExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("basic_limit_information", _JobBasicLimitInformation),
            ("io_info", _IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        ]


class _WindowsJob:
    """Own a Windows process tree until this object is closed."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects are only available on Windows")
        handle = _kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle
        try:
            limits = _JobExtendedLimitInformation()
            limits.basic_limit_information.limit_flags = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            if not _kernel32.SetInformationJobObject(
                self.handle,
                _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if not _kernel32.AssignProcessToJobObject(
                self.handle, wintypes.HANDLE(process._handle)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.handle:
            _kernel32.CloseHandle(self.handle)
            self.handle = None


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

    command = args
    payload: str | None = None
    if os.name == "nt":
        command = [sys.executable, "-c", _WINDOWS_LAUNCHER]
        payload = f"{json.dumps(args)}\n"
        popen_options["stdin"] = subprocess.PIPE

    process = subprocess.Popen(command, **popen_options)  # type: ignore[arg-type]
    job: _WindowsJob | None = None
    if os.name == "nt":
        try:
            job = _WindowsJob(process)
        except BaseException as error:
            _terminate_process_tree(process)
            stdout, stderr = _collect_after_termination(process)
            _raise_failure(args, stdout, stderr, f"could not own process tree: {error}")

    try:
        try:
            stdout, stderr = process.communicate(input=payload, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _terminate_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired as after_kill:
                stdout = _as_text(after_kill.stdout or error.stdout)
                stderr = _as_text(after_kill.stderr or error.stderr)
            _raise_failure(args, stdout, stderr, f"timed out after {timeout}s")

        if process.returncode:
            _raise_failure(
                args, stdout, stderr, f"exited with status {process.returncode}"
            )
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    finally:
        if job is not None:
            job.close()


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
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _collect_after_termination(process: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        return process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired as error:
            _raise_failure(
                process.args,
                _as_text(error.stdout),
                _as_text(error.stderr),
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
