"""Isolated process and Git helpers for developer-workflow contract tests."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, TextIO

_WINDOWS_LAUNCHER = """import json
import subprocess
import sys

payload = sys.stdin.readline()
if not payload:
    raise SystemExit(125)
raise SystemExit(subprocess.run(json.loads(payload), check=False).returncode)
"""

_POSIX_SUPERVISOR = """import json
import os
import signal
import subprocess
import sys
import traceback

result_fd = int(sys.argv[1])
command = json.loads(sys.argv[2])
try:
    returncode = subprocess.run(command, check=False).returncode
except BaseException:
    traceback.print_exc()
    returncode = 127
os.write(result_fd, f"{returncode}\\n".encode("ascii"))
os.close(result_fd)
while True:
    signal.pause()
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
    if os.name != "nt":
        return _run_posix_command(args, cwd, env, timeout)
    return _run_windows_command(args, cwd, env, timeout)


def _run_windows_command(
    args: list[str], cwd: Path, env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    popen_options: dict[str, object] = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
        "stdin": subprocess.PIPE,
    }
    command = [sys.executable, "-c", _WINDOWS_LAUNCHER]
    payload = f"{json.dumps(args)}\n"
    process = subprocess.Popen(command, **popen_options)  # type: ignore[arg-type]
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
        job.close()


def _run_posix_command(
    args: list[str], cwd: Path, env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    result_read_fd, result_write_fd = os.pipe()
    process: subprocess.Popen[str] | None = None
    reader_threads: list[threading.Thread] = []
    reader_errors: list[str] = []
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    result_reason: str | None = None
    target_returncode: int | None = None
    cleanup_error: AssertionError | None = None
    try:
        command = [
            sys.executable,
            "-c",
            _POSIX_SUPERVISOR,
            str(result_write_fd),
            json.dumps(args),
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
                pass_fds=(result_write_fd,),
            )
        finally:
            os.close(result_write_fd)
            result_write_fd = -1

        assert process.stdout is not None
        assert process.stderr is not None
        reader_threads = [
            _start_output_reader(process.stdout, stdout_chunks, reader_errors),
            _start_output_reader(process.stderr, stderr_chunks, reader_errors),
        ]
        try:
            target_returncode = _wait_for_posix_result(result_read_fd, timeout)
            if target_returncode is None:
                result_reason = f"timed out after {timeout}s"
        finally:
            cleanup_error = _kill_posix_group_then_reap(
                process,
                current_group=os.getpgrp(),
                kill_group=os.killpg,
                kill_signal=signal.SIGKILL,
            )
    finally:
        if result_write_fd >= 0:
            os.close(result_write_fd)
        os.close(result_read_fd)
        if process is not None and cleanup_error is None and process.returncode is None:
            cleanup_error = _kill_posix_group_then_reap(
                process,
                current_group=os.getpgrp(),
                kill_group=os.killpg,
                kill_signal=signal.SIGKILL,
            )
        reader_cleanup_error = _join_output_readers(
            reader_threads,
            (
                [
                    stream
                    for stream in (process.stdout, process.stderr)
                    if stream is not None
                ]
                if process is not None
                else []
            ),
            reader_errors,
        )
        if cleanup_error is None:
            cleanup_error = reader_cleanup_error

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if cleanup_error is not None:
        _raise_failure(args, stdout, stderr, f"cleanup failed: {cleanup_error}")
    if reader_errors:
        _raise_failure(
            args, stdout, stderr, f"output collection failed: {reader_errors}"
        )
    if result_reason is not None:
        _raise_failure(args, stdout, stderr, result_reason)
    if target_returncode is None:
        _raise_failure(args, stdout, stderr, "supervisor exited without a result")
    if target_returncode:
        _raise_failure(args, stdout, stderr, f"exited with status {target_returncode}")
    return subprocess.CompletedProcess(args, target_returncode, stdout, stderr)


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


def _start_output_reader(
    stream: TextIO, chunks: list[str], errors: list[str]
) -> threading.Thread:
    def drain() -> None:
        try:
            while chunk := stream.read(65536):
                chunks.append(chunk)
        except (OSError, ValueError) as error:
            errors.append(str(error))

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    return thread


def _wait_for_posix_result(result_fd: int, timeout: float) -> int | None:
    with selectors.DefaultSelector() as selector:
        selector.register(result_fd, selectors.EVENT_READ)
        events = selector.select(max(timeout, 0))
    if not events:
        return None
    result = os.read(result_fd, 64)
    if not result:
        raise AssertionError("POSIX supervisor closed its result channel unexpectedly")
    try:
        return int(result.strip())
    except ValueError as error:
        raise AssertionError(f"Invalid POSIX supervisor result: {result!r}") from error


def _kill_posix_group_then_reap(
    process: subprocess.Popen[str],
    *,
    current_group: int,
    kill_group: Callable[[int, int], None],
    kill_signal: int,
) -> AssertionError | None:
    errors: list[str] = []
    process_group = process.pid
    if process_group == current_group:
        errors.append(f"refused to kill current process group {current_group}")
    else:
        try:
            kill_group(process_group, kill_signal)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"could not kill process group {process_group}: {error}")

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"could not kill root process {process.pid}: {error}")
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            errors.append(f"could not reap root process {process.pid} within 20s")
        except OSError as error:
            errors.append(f"could not reap root process {process.pid}: {error}")
    except OSError as error:
        errors.append(f"could not reap root process {process.pid}: {error}")

    if errors:
        return AssertionError("; ".join(errors))
    return None


def _join_output_readers(
    threads: list[threading.Thread],
    streams: list[TextIO],
    errors: list[str],
) -> AssertionError | None:
    deadline = time.monotonic() + 10
    for thread in threads:
        thread.join(max(deadline - time.monotonic(), 0))
    alive = [thread for thread in threads if thread.is_alive()]
    if alive:
        for stream in streams:
            try:
                stream.close()
            except (OSError, ValueError) as error:
                errors.append(str(error))
        close_deadline = time.monotonic() + 1
        for thread in alive:
            thread.join(max(close_deadline - time.monotonic(), 0))
    for stream in streams:
        try:
            stream.close()
        except (OSError, ValueError) as error:
            errors.append(str(error))
    if any(thread.is_alive() for thread in threads):
        return AssertionError("output reader threads did not stop within 11s")
    return None


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
