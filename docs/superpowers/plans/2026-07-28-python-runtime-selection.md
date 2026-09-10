# Python Runtime Selection Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the development launcher select a Python interpreter that can load the real backend and report child-process startup failures immediately.

**Architecture:** Keep orchestration in `scripts/dev.ps1`, but separate candidate enumeration, application-import health checks, and process-aware port waiting into testable functions. Python tests invoke a dot-sourced copy of the PowerShell script and replace boundary functions with deterministic fakes, while final verification starts the real worktree without an environment override.

**Tech Stack:** PowerShell 5.1, Python 3.10+/pytest, FastAPI/Uvicorn, Next.js.

---

## File Map

- Modify `scripts/dev.ps1`: dependency-aware interpreter selection, candidate diagnostics, dot-source guard, and process-aware startup wait.
- Modify `tests/test_dev_script_boundaries.py`: structural guards for the new selection and startup behavior.
- Create `tests/test_dev_python_selection.py`: behavioral PowerShell tests for interpreter fallback, install-mode selection, and early process exit.

### Task 1: Select a backend-capable Python interpreter

**Files:**

- Modify: `scripts/dev.ps1:41-105, 469-505, 570-575, 628-640, 788-805`
- Modify: `tests/test_dev_script_boundaries.py`
- Create: `tests/test_dev_python_selection.py`

- [x] **Step 1: Add a reusable PowerShell test runner**

Create a pytest helper that dot-sources `scripts/dev.ps1`, overrides selected PowerShell functions, evaluates an expression, and returns stdout:

```python
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = PROJECT_ROOT / "scripts" / "dev.ps1"


def _run_powershell(body: str) -> subprocess.CompletedProcess[str]:
    script = f". '{DEV_SCRIPT}'; $ErrorActionPreference = 'Stop'; {body}"
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
```

Add a source-boundary test requiring the final dispatcher to be guarded when dot-sourced:

```python
assert "$MyInvocation.InvocationName -ne '.'" in source
```

- [x] **Step 2: Add failing interpreter-selection behavior tests**

Override candidate and probe functions in PowerShell so the first interpreter is runnable but cannot import the app and the second is healthy:

```python
def test_runtime_selection_skips_runnable_interpreter_that_cannot_import_app():
    result = _run_powershell(
        """
        function Get-ProjectPythonCandidates { @('broken-python', 'healthy-python') }
        function Test-PythonRunnable { param($PythonExe) return $true }
        function Test-BackendApplicationImport {
            param($PythonExe, $ProjectRoot)
            return $PythonExe -eq 'healthy-python'
        }
        Resolve-ProjectPython -ProjectRoot '.' -RequireBackendDependencies
        """
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "healthy-python"
```

Add a second test without `-RequireBackendDependencies` and assert `broken-python` is returned for install mode. Add a third test where neither candidate is healthy and assert the result is empty and diagnostic entries identify both rejected candidates.

- [x] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_dev_python_selection.py tests/test_dev_script_boundaries.py
```

Expected: FAIL because the script invokes its dispatcher when dot-sourced and the new candidate/import functions or switch do not exist.

- [x] **Step 4: Add candidate enumeration and real import probing**

Replace inline candidate construction with:

```powershell
function Get-ProjectPythonCandidates {
    param([string]$ProjectRoot)
    # Return de-duplicated candidates in the existing priority order.
}

function Test-BackendApplicationImport {
    param([string]$PythonExe, [string]$ProjectRoot)
    Push-Location -LiteralPath $ProjectRoot
    try {
        & $PythonExe -c "import app.main" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch { return $false }
    finally { Pop-Location }
}
```

Extend `Resolve-ProjectPython`:

```powershell
function Resolve-ProjectPython {
    param(
        [string]$ProjectRoot,
        [switch]$RequireBackendDependencies,
        [ref]$RejectedCandidates
    )
    foreach ($candidate in (Get-ProjectPythonCandidates -ProjectRoot $ProjectRoot)) {
        if (-not (Test-PythonRunnable $candidate)) { continue }
        if (-not $RequireBackendDependencies -or
            (Test-BackendApplicationImport -PythonExe $candidate -ProjectRoot $ProjectRoot)) {
            return $candidate
        }
        if ($RejectedCandidates) { $RejectedCandidates.Value += $candidate }
    }
    return $null
}
```

De-duplicate candidates case-insensitively without resolving command names into paths before testing them.

- [x] **Step 5: Use healthy selection in doctor, start, and status**

`Invoke-Doctor` and `Invoke-Start` call `Resolve-ProjectPython -RequireBackendDependencies`. `Invoke-Install` calls it without the switch. `Invoke-Status` prefers the Python recorded in runtime metadata for running services; otherwise it resolves a healthy interpreter.

When candidates are rejected, doctor prints one warning per interpreter. If no healthy interpreter exists, use:

```text
No Python interpreter can import app.main. Run scripts\dev.ps1 install or set BILIBILI_RAG_PYTHON.
```

- [x] **Step 6: Guard normal dispatch when dot-sourced**

Replace the unconditional final call with:

```powershell
if ($MyInvocation.InvocationName -ne ".") {
    Invoke-CommandByName -Command $Command
}
```

- [x] **Step 7: Run tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_dev_python_selection.py tests/test_dev_script_boundaries.py
```

Expected: all tests pass; the fallback test selects `healthy-python`, while install-mode selection returns `broken-python`.

- [x] **Step 8: Commit interpreter selection**

```powershell
git add scripts/dev.ps1 tests/test_dev_script_boundaries.py tests/test_dev_python_selection.py
git commit -m "fix: select a healthy backend Python runtime"
```

### Task 2: Fail immediately when a startup child exits

**Files:**

- Modify: `scripts/dev.ps1:431-447, 674-691`
- Modify: `tests/test_dev_python_selection.py`

- [x] **Step 1: Add a failing early-exit test**

Start a real PowerShell child that exits with code 23, wait for it, and call the new process-aware helper with a long nominal timeout. Assert it returns false in under two seconds and exposes exit code 23:

```python
def test_wait_port_stops_when_child_process_exits():
    result = _run_powershell(
        """
        function Test-PortListening { param($Port) return $false }
        $child = Start-Process powershell -ArgumentList @('-NoProfile','-Command','exit 23') -PassThru
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $ready = Wait-Port -Port 65530 -TimeoutSeconds 30 -Process $child
        $child.WaitForExit()
        Write-Output "$ready|$($child.ExitCode)|$($watch.ElapsedMilliseconds)"
        """
    )
    assert result.returncode == 0, result.stderr
    ready, exit_code, elapsed = result.stdout.strip().split("|")
    assert ready == "False"
    assert exit_code == "23"
    assert int(elapsed) < 2000
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest -q tests/test_dev_python_selection.py::test_wait_port_stops_when_child_process_exits
```

Expected: FAIL because `Wait-Port` does not accept `-Process` and waits by timeout only.

- [x] **Step 3: Add process-aware waiting**

Extend `Wait-Port` with an optional `System.Diagnostics.Process` parameter. On every poll, refresh the process and return false immediately when `HasExited` is true:

```powershell
if ($Process) {
    $Process.Refresh()
    if ($Process.HasExited) { return $false }
}
```

Keep the existing one-second polling interval and port-ready behavior.

- [x] **Step 4: Pass child processes and report exit codes**

Pass `$backendProcess` and `$frontendProcess` to their respective `Wait-Port` calls. When readiness fails, show both output and error logs, then distinguish early exit from timeout:

```powershell
if ($backendProcess.HasExited) {
    throw "Backend exited before port 8000 was ready (exit code $($backendProcess.ExitCode))."
}
throw "Backend did not become ready on port 8000."
```

Apply the same pattern to the frontend process.

- [x] **Step 5: Run focused and repository tests**

Run:

```powershell
python -m pytest -q tests/test_dev_python_selection.py tests/test_dev_script_boundaries.py
python -m pytest -q tests
```

Expected: all tests pass.

- [x] **Step 6: Commit fast failure**

```powershell
git add scripts/dev.ps1 tests/test_dev_python_selection.py
git commit -m "fix: fail fast when development services exit"
```

### Task 3: Verify the real launcher and publish

**Files:**

- Verification only.

- [x] **Step 1: Stop the temporary runtime**

Run from the worktree:

```powershell
& .\scripts\dev.ps1 stop
```

Expected: ports 8000 and 3000 are free.

- [x] **Step 2: Verify doctor selects the healthy interpreter**

Clear only the process-level override and run doctor:

```powershell
Remove-Item Env:BILIBILI_RAG_PYTHON -ErrorAction SilentlyContinue
& .\scripts\dev.ps1 doctor
```

Expected: doctor warns that the incomplete Conda interpreter was rejected and reports Python 3.12 as healthy.

- [x] **Step 3: Start through the worktree batch file without overrides**

```powershell
cmd.exe /d /c "启动.bat -NoBrowser"
```

Expected: command exits zero, runtime metadata records the Python 3.12 executable, and both ports become ready.

- [x] **Step 4: Verify health and status**

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/docs -TimeoutSec 5).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:3000 -TimeoutSec 10).StatusCode
& .\scripts\dev.ps1 status
```

Expected: both HTTP status codes are 200; status reports both processes running and the runtime Python is Python 3.12.

- [x] **Step 5: Run repository verification**

```powershell
& .\scripts\verify-before-commit.ps1
```

Expected: backend tests, frontend tests, lint, formatting, and production build pass.

- [x] **Step 6: Push the existing branch**

```powershell
git status --short
git push origin agent/video-note-ui-polish
```

Expected: worktree is clean and `origin/agent/video-note-ui-polish` advances without force-push. Leave the verified services running for the user.
