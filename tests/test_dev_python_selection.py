import json
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = PROJECT_ROOT / "scripts" / "dev.ps1"


def _run_dev_functions(body: str) -> subprocess.CompletedProcess[str]:
    escaped_path = str(DEV_SCRIPT).replace("'", "''")
    return subprocess.run(
        [
            "powershell.exe",
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
        "rejected": ["broken-python"],
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
        "rejected": ["not-runnable", "missing-app"],
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
