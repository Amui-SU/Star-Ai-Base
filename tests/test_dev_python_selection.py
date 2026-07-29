import json
from pathlib import Path
import shutil
import subprocess

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = PROJECT_ROOT / "scripts" / "dev.ps1"
POWERSHELL = shutil.which("powershell.exe")


def _function_block(source: str, name: str) -> str:
    marker = f"function {name} "
    start = source.index(marker)
    next_start = source.find("\nfunction ", start + len(marker))
    return source[start:] if next_start == -1 else source[start:next_start]


def _run_dev_functions(body: str) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.skip("requires powershell.exe")

    escaped_path = str(DEV_SCRIPT).replace("'", "''")
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f". '{escaped_path}'; {body}",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run_selection(body: str) -> dict:
    result = _run_dev_functions(body)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


def test_healthy_resolution_skips_runnable_python_that_cannot_import_application():
    result = _run_selection(
        r"""
        function Get-ProjectPythonCandidates { @('broken-python', 'healthy-python') }
        function Test-PythonRunnable { param($PythonExe) return $true }
        function Test-BackendApplicationImport {
            param($PythonExe, $ProjectRoot)
            return $PythonExe -eq 'healthy-python'
        }
        $rejected = @()
        $resolved = Resolve-ProjectPython -ProjectRoot '.' -RequireBackendDependencies -RejectedCandidates ([ref]$rejected)
        [pscustomobject]@{ resolved = $resolved; rejected = @($rejected) } | ConvertTo-Json -Compress
        """
    )

    assert result == {
        "resolved": "healthy-python",
        "rejected": [
            {
                "candidate": "broken-python",
                "reason": "cannot import app.main",
            }
        ],
    }


def test_install_resolution_returns_first_runnable_python_without_import_probe():
    result = _run_selection(
        r"""
        function Get-ProjectPythonCandidates { @('broken-python', 'healthy-python') }
        function Test-PythonRunnable { param($PythonExe) return $true }
        function Test-BackendApplicationImport { throw 'install must not probe app imports' }
        $rejected = @()
        $resolved = Resolve-ProjectPython -ProjectRoot '.' -RejectedCandidates ([ref]$rejected)
        [pscustomobject]@{ resolved = $resolved; rejected = @($rejected) } | ConvertTo-Json -Compress
        """
    )

    assert result == {"resolved": "broken-python", "rejected": []}


def test_selected_path_command_is_normalized_to_its_executable_source():
    result = _run_selection(
        r"""
        function Get-ProjectPythonCandidates { @('python') }
        function Test-PythonRunnable { return $true }
        function Test-BackendApplicationImport { return $true }
        $expected = (Get-Command python -CommandType Application | Select-Object -First 1).Source
        $resolved = Resolve-ProjectPython -ProjectRoot '.' -RequireBackendDependencies
        [pscustomobject]@{ resolved = $resolved; expected = $expected } | ConvertTo-Json -Compress
        """
    )

    assert result["resolved"] == result["expected"]
    assert Path(result["resolved"]).is_absolute()


def test_selected_literal_executable_path_is_preserved():
    result = _run_selection(
        r"""
        $literalPath = 'C:\fake-python\python.exe'
        function Get-ProjectPythonCandidates { @($literalPath) }
        function Test-PythonRunnable { return $true }
        function Test-BackendApplicationImport { return $true }
        $resolved = Resolve-ProjectPython -ProjectRoot '.' -RequireBackendDependencies
        [pscustomobject]@{ resolved = $resolved; expected = $literalPath } | ConvertTo-Json -Compress
        """
    )

    assert result == {
        "resolved": r"C:\fake-python\python.exe",
        "expected": r"C:\fake-python\python.exe",
    }


def test_healthy_resolution_returns_null_and_reports_every_rejected_candidate():
    result = _run_selection(
        r"""
        function Get-ProjectPythonCandidates { @('not-runnable', 'missing-app') }
        function Test-PythonRunnable { param($PythonExe) return $PythonExe -ne 'not-runnable' }
        function Test-BackendApplicationImport { param($PythonExe, $ProjectRoot) return $false }
        $rejected = @()
        $resolved = Resolve-ProjectPython -ProjectRoot '.' -RequireBackendDependencies -RejectedCandidates ([ref]$rejected)
        [pscustomobject]@{ resolved = $resolved; rejected = @($rejected) } | ConvertTo-Json -Compress
        """
    )

    assert result == {
        "resolved": None,
        "rejected": [
            {"candidate": "missing-app", "reason": "cannot import app.main"},
        ],
    }


def test_status_reports_runnable_python_recorded_for_existing_runtime():
    result = _run_dev_functions(
        r"""
        function Read-RuntimeState {
            [pscustomobject]@{
                python = 'runtime-python'
                backend = $null
                frontend = $null
            }
        }
        function Resolve-ProjectPython { throw 'must not reselect while runtime Python is valid' }
        function Test-PythonRunnable { param($PythonExe) return $PythonExe -eq 'runtime-python' }
        function runtime-python { 'Python fake-runtime' }
        function Test-CommandExists { return $false }
        function Test-PortListening { return $false }
        Invoke-Status -ProjectRoot '.'
        """
    )

    assert result.returncode == 0, result.stderr
    assert "(runtime-python)" in result.stdout


def test_status_reports_unavailable_recorded_runtime_python_without_reselecting():
    result = _run_dev_functions(
        r"""
        function Read-RuntimeState {
            [pscustomobject]@{
                python = 'missing-runtime-python'
                backend = $null
                frontend = $null
            }
        }
        function Resolve-ProjectPython { throw 'must not reselect when runtime metadata records Python' }
        function Test-PythonRunnable { return $false }
        function Test-CommandExists { return $false }
        function Test-PortListening { return $false }
        Invoke-Status -ProjectRoot '.'
        """
    )

    assert result.returncode == 0, result.stderr
    assert "Python: unavailable (recorded: missing-runtime-python)" in result.stdout


def test_rejected_candidate_warnings_state_the_exact_failure_reason():
    result = _run_dev_functions(
        r"""
        $rejected = @(
            [pscustomobject]@{ candidate = 'missing-app'; reason = 'cannot import app.main' }
        )
        Write-RejectedPythonCandidates -Candidates $rejected
        """
    )

    assert result.returncode == 0, result.stderr
    assert (
        "Rejected Python candidate: missing-app (cannot import app.main)"
        in result.stdout
    )


def test_wait_port_returns_promptly_when_child_process_exits():
    result = _run_dev_functions(
        r"""
        $ErrorActionPreference = 'Stop'
        function Test-PortListening { param([int]$Port) return $false }
        $child = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile', '-Command', 'exit 23') `
            -WindowStyle Hidden `
            -PassThru
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $ready = Wait-Port -Port 65530 -TimeoutSeconds 30 -Process $child
        $stopwatch.Stop()
        $child.WaitForExit()
        [pscustomobject]@{
            ready = [bool]$ready
            exitCode = $child.ExitCode
            elapsedMs = $stopwatch.ElapsedMilliseconds
        } | ConvertTo-Json -Compress
        """
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["ready"] is False
    assert payload["exitCode"] == 23
    assert payload["elapsedMs"] < 2000


def test_start_waits_on_each_child_and_reports_early_exit_codes():
    start_block = _function_block(
        DEV_SCRIPT.read_text(encoding="utf-8"), "Invoke-Start"
    )

    assert (
        "Wait-Port -Port 8000 -TimeoutSeconds 60 -Process $backendProcess"
        in start_block
    )
    assert (
        "Wait-Port -Port 3000 -TimeoutSeconds 60 -Process $frontendProcess"
        in start_block
    )
    assert (
        'throw "Backend exited before port 8000 was ready '
        '(exit code $($backendProcess.ExitCode))."' in start_block
    )
    assert (
        'throw "Frontend exited before port 3000 was ready '
        '(exit code $($frontendProcess.ExitCode))."' in start_block
    )
