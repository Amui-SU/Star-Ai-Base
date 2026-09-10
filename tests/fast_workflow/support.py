import os
import re
import signal
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VerifierRepo = tuple[Path, dict[str, str]]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def markdown_section(document: str, heading: str) -> str:
    marker = heading.split(maxsplit=1)[0]
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", document)
    assert match is not None, f"missing Markdown section: {heading}"
    remainder = document[match.end() :]
    next_heading = re.search(rf"(?m)^#{{1,{len(marker)}}}\s+", remainder)
    if next_heading is None:
        return remainder
    return remainder[: next_heading.start()]


def powershell_executable() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required for verifier CLI contract tests")
    return executable


def isolated_subprocess_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    git_config = tmp_path / "empty.gitconfig"
    git_config.write_text("", encoding="utf-8")
    environment["GIT_CONFIG_GLOBAL"] = str(git_config)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except Exception:
        pass

    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        pass

    try:
        process.wait(timeout=5)
    except Exception:
        pass


def timeout_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_subprocess_with_timeout(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    popen_options: dict[str, object] = {}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **popen_options,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as initial_timeout:
        terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as cleanup_timeout:
            try:
                process.kill()
            except Exception:
                pass
            stdout = timeout_stream_text(
                cleanup_timeout.output
                if cleanup_timeout.output is not None
                else initial_timeout.output
            )
            stderr = timeout_stream_text(
                cleanup_timeout.stderr
                if cleanup_timeout.stderr is not None
                else initial_timeout.stderr
            )
        raise AssertionError(
            f"subprocess timed out after {timeout_seconds}s: "
            f"args={command!r}\nstdout={stdout!r}\nstderr={stderr!r}"
        ) from None

    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )


def run_checked(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    result = run_subprocess_with_timeout(
        command,
        cwd=cwd,
        environment=environment,
        timeout_seconds=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def run_verifier(
    repo: Path,
    environment: dict[str, str],
    *arguments: str,
    executable: str | None = None,
) -> subprocess.CompletedProcess[str]:
    shell = executable or powershell_executable()
    command = [shell, "-NoProfile"]
    if Path(shell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", "scripts/verify-fast.ps1", *arguments])
    return run_subprocess_with_timeout(
        command,
        cwd=repo,
        environment=environment,
        timeout_seconds=60,
    )


def write_frontend_stub(repo: Path, executable: str) -> Path:
    bin_directory = repo / "frontend" / "node_modules" / ".bin"
    bin_directory.mkdir(parents=True)
    suffix = ".cmd" if os.name == "nt" else ""
    stub = bin_directory / f"{executable}{suffix}"

    if os.name == "nt":
        stub.write_text(
            "@echo off\r\n"
            'echo %* > "%FAST_VERIFIER_LOG%"\r\n'
            "exit /b %FAST_VERIFIER_EXIT%\r\n",
            encoding="utf-8",
        )
    else:
        stub.write_text(
            "#!/bin/sh\n"
            'printf \'%s\\n\' "$@" > "$FAST_VERIFIER_LOG"\n'
            'exit "${FAST_VERIFIER_EXIT:-0}"\n',
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

    return stub


def write_frontend_target(repo: Path, relative_path: str) -> Path:
    target = repo / "frontend" / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("export {};\n", encoding="utf-8")
    return target
