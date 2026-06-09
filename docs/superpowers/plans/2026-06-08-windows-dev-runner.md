# Windows Dev Runner Implementation Plan

> **STATUS: COMPLETED** — All 10 tasks implemented, reviewed, and merged to `main` (2026-06-08).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-only local dev runner that installs dependencies, starts, stops, checks, and diagnoses the backend/frontend services with one maintainable PowerShell entry point.

**Architecture:** Add `scripts/dev.ps1` as the canonical process manager and keep BAT files as thin wrappers. The script resolves the project root, selects one Python consistently, validates backend/frontend dependencies, starts services with logs, records runtime metadata, and shuts down only project-owned processes.

**Tech Stack:** Windows PowerShell, BAT wrappers, FastAPI/uvicorn backend, Next.js frontend, npm, pip, JSON runtime metadata.

---

## File Structure

- Create `scripts/dev.ps1`: canonical Windows dev runner with commands `doctor`, `install`, `start`, `stop`, `restart`, `status`, and `logs`.
- Modify `安装依赖.bat`: call `scripts\dev.ps1 install` instead of `setup_dependencies.ps1` directly.
- Keep `setup_dependencies.ps1`: leave as a compatibility installer for this phase because it was already aligned to the same Python selection logic.
- Create `启动.bat`: thin wrapper for `scripts\dev.ps1 start`.
- Create `停止.bat`: thin wrapper for `scripts\dev.ps1 stop`.
- Create `状态.bat`: thin wrapper for `scripts\dev.ps1 status`.
- Create `日志.bat`: thin wrapper for `scripts\dev.ps1 logs`.
- Modify `README.md`: document the new canonical Windows startup workflow.

Runtime files:

- `logs\backend-start.log`
- `logs\frontend-start.log`
- `logs\runtime.json`

These runtime files are generated state and must not be committed.

## Task 1: PowerShell Runner Foundation

**Files:**

- Create: `scripts/dev.ps1`

- [ ] **Step 1: Create the runner skeleton**

Add `scripts/dev.ps1`:

```powershell
param(
    [ValidateSet("doctor", "install", "start", "stop", "restart", "status", "logs")]
    [string]$Command = "doctor",
    [switch]$SkipFrontend,
    [switch]$NoBrowser,
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-WarnMsg($Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail($Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-FrontendPath {
    param([string]$ProjectRoot)
    return Join-Path $ProjectRoot "frontend"
}

function Get-LogsPath {
    param([string]$ProjectRoot)
    return Join-Path $ProjectRoot "logs"
}

function Get-RuntimePath {
    param([string]$ProjectRoot)
    return Join-Path (Get-LogsPath $ProjectRoot) "runtime.json"
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Invoke-CommandByName {
    param([string]$Command)

    $projectRoot = Get-ProjectRoot
    switch ($Command) {
        "doctor" { Invoke-Doctor -ProjectRoot $projectRoot }
        "install" { Invoke-Install -ProjectRoot $projectRoot -SkipFrontend:$SkipFrontend }
        "start" { Invoke-Start -ProjectRoot $projectRoot -NoBrowser:$NoBrowser }
        "stop" { Invoke-Stop -ProjectRoot $projectRoot }
        "restart" {
            Invoke-Stop -ProjectRoot $projectRoot
            Invoke-Start -ProjectRoot $projectRoot -NoBrowser:$NoBrowser
        }
        "status" { Invoke-Status -ProjectRoot $projectRoot }
        "logs" { Invoke-Logs -ProjectRoot $projectRoot -Follow:$Follow }
    }
}
```

- [ ] **Step 2: Run parser check**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$null = [scriptblock]::Create((Get-Content -Raw scripts\dev.ps1)); 'parse ok'"
```

Expected:

```text
parse ok
```

- [ ] **Step 3: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner skeleton"
```

## Task 2: Environment Resolution and Doctor

**Files:**

- Modify: `scripts/dev.ps1`

- [ ] **Step 1: Add helper functions**

Add these functions before `Invoke-CommandByName`:

```powershell
function Test-CommandExists {
    param([string]$CommandName)
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-PythonRunnable {
    param([string]$PythonExe)
    try {
        & $PythonExe --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-ProjectPython {
    param([string]$ProjectRoot)

    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot "venv\Scripts\python.exe")
    )

    $envPython = [Environment]::GetEnvironmentVariable("BILIBILI_RAG_PYTHON", "Process")
    if (-not $envPython) {
        $envPython = [Environment]::GetEnvironmentVariable("BILIBILI_RAG_PYTHON", "User")
    }
    if (-not $envPython) {
        $envPython = [Environment]::GetEnvironmentVariable("BILIBILI_RAG_PYTHON", "Machine")
    }
    if ($envPython) {
        $candidates += $envPython
    }

    $candidates += "C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe"
    if (Test-CommandExists "python") {
        $candidates += "python"
    }

    foreach ($candidate in $candidates) {
        if (($candidate -eq "python" -or (Test-Path $candidate)) -and (Test-PythonRunnable $candidate)) {
            return $candidate
        }
    }

    return $null
}

function Test-BackendDependencies {
    param([string]$PythonExe)

    $code = "import fastapi, uvicorn, cryptography, jose; from passlib.context import CryptContext; CryptContext(schemes=['bcrypt'], deprecated='auto').hash('dependency-check')"
    & $PythonExe -c $code *> $null
    return $LASTEXITCODE -eq 0
}

function Test-FfmpegRunnable {
    try {
        ffmpeg -version *> $null
        return $true
    }
    catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)

    $result = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    return [bool]$result
}
```

- [ ] **Step 2: Add doctor command**

Add:

```powershell
function Invoke-Doctor {
    param([string]$ProjectRoot)

    $frontendPath = Get-FrontendPath $ProjectRoot
    $logsPath = Get-LogsPath $ProjectRoot
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    Write-Info "Project root: $ProjectRoot"

    if (Test-Path $ProjectRoot) { Write-Ok "Project root exists." } else { Write-Fail "Project root missing."; return }
    if (Test-Path $frontendPath) { Write-Ok "Frontend directory exists." } else { Write-Fail "Frontend directory missing: $frontendPath" }

    if ($pythonExe) {
        $pythonVersion = & $pythonExe --version 2>&1
        Write-Ok "Python: $pythonVersion ($pythonExe)"
        if (Test-BackendDependencies $pythonExe) {
            Write-Ok "Backend dependencies are healthy."
        }
        else {
            Write-Fail "Backend dependencies are incomplete. Run: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 install"
        }
    }
    else {
        Write-Fail "No runnable Python found. Install Python or set BILIBILI_RAG_PYTHON."
    }

    if (Test-CommandExists "node") {
        Write-Ok "Node.js: $(node --version)"
    }
    else {
        Write-Fail "Node.js is missing."
    }

    if (Test-CommandExists "npm") {
        Write-Ok "npm: $(npm --version)"
    }
    else {
        Write-Fail "npm is missing."
    }

    if (Test-Path (Join-Path $frontendPath "node_modules")) {
        Write-Ok "Frontend dependencies are installed."
    }
    else {
        Write-WarnMsg "frontend\node_modules is missing. Run install before start."
    }

    if (Test-FfmpegRunnable) {
        Write-Ok "ffmpeg is available."
    }
    else {
        Write-WarnMsg "ffmpeg is missing. ASR local fallback may not work."
    }

    Ensure-Directory $logsPath
    Write-Ok "Logs directory is writable: $logsPath"

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            Write-WarnMsg "Port $port is already listening. Run status to inspect ownership."
        }
        else {
            Write-Ok "Port $port is free."
        }
    }
}
```

Add this as the final line in the script:

```powershell
Invoke-CommandByName -Command $Command
```

- [ ] **Step 3: Run doctor**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor
```

Expected:

```text
[INFO] Project root: ...
[OK]   Python: ...
```

The command can show warnings for missing `frontend\node_modules` or ffmpeg, but must not crash.

- [ ] **Step 4: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner doctor"
```

## Task 3: Install Command

**Files:**

- Modify: `scripts/dev.ps1`
- Modify: `安装依赖.bat`

- [ ] **Step 1: Add install command**

Add before `Invoke-CommandByName`:

```powershell
function Invoke-Install {
    param(
        [string]$ProjectRoot,
        [bool]$SkipFrontend = $false
    )

    $frontendPath = Get-FrontendPath $ProjectRoot
    $requirementsPath = Join-Path $ProjectRoot "requirements.txt"
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    if (-not $pythonExe) {
        throw "No runnable Python found. Install Python or set BILIBILI_RAG_PYTHON."
    }
    if (-not (Test-Path $requirementsPath)) {
        throw "Missing requirements file: $requirementsPath"
    }
    if (-not (Test-Path $frontendPath)) {
        throw "Missing frontend directory: $frontendPath"
    }

    Write-Ok "Using Python: $(& $pythonExe --version 2>&1) ($pythonExe)"
    Write-Info "Upgrading pip..."
    & $pythonExe -m pip install --upgrade pip

    Write-Info "Installing backend dependencies..."
    & $pythonExe -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }

    if (-not $SkipFrontend) {
        if (-not (Test-CommandExists "npm")) {
            throw "npm is missing. Install Node.js LTS."
        }
        Write-Info "Installing frontend dependencies..."
        Push-Location $frontendPath
        try {
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency installation failed."
            }
        }
        finally {
            Pop-Location
        }
    }

    Write-Ok "Dependency installation completed."
}
```

- [ ] **Step 2: Update 安装依赖.bat**

Replace the PowerShell call in `安装依赖.bat` with:

```bat
powershell -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\dev.ps1" install
```

Keep the existing project-root checks and error handling.

- [ ] **Step 3: Run install without frontend**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 install -SkipFrontend
```

Expected:

```text
[OK]   Dependency installation completed.
```

- [ ] **Step 4: Run dependency checks**

Run:

```powershell
C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe -m pip check
```

Expected:

```text
No broken requirements found.
```

- [ ] **Step 5: Commit**

```powershell
git add scripts\dev.ps1 安装依赖.bat
git commit -m "feat: add windows dev runner install"
```

## Task 4: Runtime Metadata and Process Utilities

**Files:**

- Modify: `scripts/dev.ps1`

- [ ] **Step 1: Add process and metadata helpers**

Add before command functions:

```powershell
function Get-ProcessCommandLine {
    param([int]$ProcessId)
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($proc) { return "" + $proc.CommandLine }
    return ""
}

function Test-ProjectProcess {
    param(
        [int]$ProcessId,
        [string]$ProjectRoot
    )

    $cmd = (Get-ProcessCommandLine -ProcessId $ProcessId).ToLowerInvariant()
    $root = $ProjectRoot.ToLowerInvariant()
    return $cmd.Contains($root)
}

function Save-RuntimeState {
    param(
        [string]$ProjectRoot,
        [System.Diagnostics.Process]$BackendProcess,
        [System.Diagnostics.Process]$FrontendProcess,
        [string]$PythonExe
    )

    $runtime = [ordered]@{
        project_root = $ProjectRoot
        python = $PythonExe
        backend = [ordered]@{
            pid = $BackendProcess.Id
            port = 8000
            command = "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
            started_at = (Get-Date).ToString("o")
        }
        frontend = [ordered]@{
            pid = $FrontendProcess.Id
            port = 3000
            command = "npm run dev"
            started_at = (Get-Date).ToString("o")
        }
    }

    $runtimePath = Get-RuntimePath $ProjectRoot
    Ensure-Directory (Split-Path $runtimePath)
    $runtime | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $runtimePath -Encoding UTF8
}

function Read-RuntimeState {
    param([string]$ProjectRoot)

    $runtimePath = Get-RuntimePath $ProjectRoot
    if (-not (Test-Path $runtimePath)) {
        return $null
    }
    return Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
}

function Remove-RuntimeState {
    param([string]$ProjectRoot)

    $runtimePath = Get-RuntimePath $ProjectRoot
    Remove-Item -LiteralPath $runtimePath -Force -ErrorAction SilentlyContinue
}

function Wait-Port {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-PortListening $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Show-LogTail {
    param(
        [string]$Path,
        [int]$Tail = 40
    )

    if (Test-Path $Path) {
        Write-Info "Last $Tail lines: $Path"
        Get-Content -LiteralPath $Path -Tail $Tail
    }
    else {
        Write-WarnMsg "Log file does not exist: $Path"
    }
}
```

- [ ] **Step 2: Run parser check**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$null = [scriptblock]::Create((Get-Content -Raw scripts\dev.ps1)); 'parse ok'"
```

Expected:

```text
parse ok
```

- [ ] **Step 3: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner runtime state"
```

## Task 5: Start Command

**Files:**

- Modify: `scripts/dev.ps1`

- [ ] **Step 1: Add start command**

Add:

```powershell
function Invoke-Start {
    param(
        [string]$ProjectRoot,
        [bool]$NoBrowser = $false
    )

    $frontendPath = Get-FrontendPath $ProjectRoot
    $logsPath = Get-LogsPath $ProjectRoot
    $backendLog = Join-Path $logsPath "backend-start.log"
    $backendErrLog = Join-Path $logsPath "backend-start.err.log"
    $frontendLog = Join-Path $logsPath "frontend-start.log"
    $frontendErrLog = Join-Path $logsPath "frontend-start.err.log"
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    if (-not $pythonExe) {
        throw "No runnable Python found. Run scripts\dev.ps1 doctor."
    }
    if (-not (Test-BackendDependencies $pythonExe)) {
        throw "Backend dependencies are incomplete. Run scripts\dev.ps1 install."
    }
    if (-not (Test-CommandExists "npm")) {
        throw "npm is missing. Install Node.js LTS."
    }
    if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
        throw "Frontend dependencies are missing. Run scripts\dev.ps1 install."
    }

    Ensure-Directory $logsPath
    Invoke-Stop -ProjectRoot $ProjectRoot -Quiet

    Remove-Item -LiteralPath $backendLog, $backendErrLog, $frontendLog, $frontendErrLog -Force -ErrorAction SilentlyContinue

    Write-Info "Starting backend..."
    $backendEnv = @{
        PYTHONIOENCODING = "utf-8"
        PYTHONUTF8 = "1"
    }
    foreach ($key in $backendEnv.Keys) {
        [Environment]::SetEnvironmentVariable($key, $backendEnv[$key], "Process")
    }

    $backendProcess = Start-Process -FilePath $pythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $backendLog `
        -RedirectStandardError $backendErrLog `
        -WindowStyle Hidden `
        -PassThru

    Write-Info "Starting frontend..."
    $frontendProcess = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/d", "/c", "npm run dev") `
        -WorkingDirectory $frontendPath `
        -RedirectStandardOutput $frontendLog `
        -RedirectStandardError $frontendErrLog `
        -WindowStyle Hidden `
        -PassThru

    if (-not (Wait-Port -Port 8000 -TimeoutSeconds 60)) {
        Show-LogTail $backendLog
        Show-LogTail $backendErrLog
        throw "Backend did not become ready on port 8000."
    }

    if (-not (Wait-Port -Port 3000 -TimeoutSeconds 60)) {
        Show-LogTail $frontendLog
        Show-LogTail $frontendErrLog
        throw "Frontend did not become ready on port 3000."
    }

    Save-RuntimeState -ProjectRoot $ProjectRoot -BackendProcess $backendProcess -FrontendProcess $frontendProcess -PythonExe $pythonExe
    Write-Ok "Backend ready: http://127.0.0.1:8000"
    Write-Ok "Frontend ready: http://localhost:3000"

    if (-not $NoBrowser) {
        Start-Process "http://localhost:3000"
    }
}
```

Update `Invoke-Stop` calls later in Task 6 to support `-Quiet`; until then parser will fail if `Invoke-Stop` is missing. To keep this task independently runnable, add a temporary no-op stop function if Task 6 is not implemented immediately:

```powershell
function Invoke-Stop {
    param(
        [string]$ProjectRoot,
        [switch]$Quiet
    )

    if (-not $Quiet) {
        Write-WarnMsg "Stop command not implemented yet."
    }
}
```

Task 6 replaces this no-op implementation.

- [ ] **Step 2: Run start smoke test**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start -NoBrowser
```

Expected:

```text
[OK]   Backend ready: http://127.0.0.1:8000
[OK]   Frontend ready: http://localhost:3000
```

- [ ] **Step 3: Inspect runtime state**

Run:

```powershell
Get-Content logs\runtime.json -Raw
```

Expected JSON contains:

```json
"project_root"
"backend"
"frontend"
"python"
```

- [ ] **Step 4: Stop manually for this task**

Until Task 6 is implemented, stop by runtime PIDs:

```powershell
$runtime = Get-Content logs\runtime.json -Raw | ConvertFrom-Json
Stop-Process -Id $runtime.backend.pid,$runtime.frontend.pid -Force -ErrorAction SilentlyContinue
Remove-Item logs\runtime.json -Force -ErrorAction SilentlyContinue
```

- [ ] **Step 5: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner start"
```

## Task 6: Stop and Status Commands

**Files:**

- Modify: `scripts/dev.ps1`

- [ ] **Step 1: Replace no-op stop command**

Replace the temporary `Invoke-Stop` with:

```powershell
function Stop-ProjectPid {
    param(
        [int]$ProcessId,
        [string]$ProjectRoot,
        [switch]$Quiet
    )

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        return
    }

    if (-not (Test-ProjectProcess -ProcessId $ProcessId -ProjectRoot $ProjectRoot)) {
        if (-not $Quiet) {
            Write-WarnMsg "Refusing to stop PID $ProcessId because it is not owned by this project."
        }
        return
    }

    Stop-Process -Id $ProcessId -Force
    if (-not $Quiet) {
        Write-Ok "Stopped PID $ProcessId."
    }
}

function Invoke-Stop {
    param(
        [string]$ProjectRoot,
        [switch]$Quiet
    )

    $runtime = Read-RuntimeState $ProjectRoot
    if ($runtime) {
        if ($runtime.backend -and $runtime.backend.pid) {
            Stop-ProjectPid -ProcessId ([int]$runtime.backend.pid) -ProjectRoot $ProjectRoot -Quiet:$Quiet
        }
        if ($runtime.frontend -and $runtime.frontend.pid) {
            Stop-ProjectPid -ProcessId ([int]$runtime.frontend.pid) -ProjectRoot $ProjectRoot -Quiet:$Quiet
        }
        Remove-RuntimeState $ProjectRoot
    }

    $root = $ProjectRoot.ToLowerInvariant()
    $processes = Get-CimInstance Win32_Process | Where-Object {
        ("" + $_.CommandLine).ToLowerInvariant().Contains($root) -and
        ($_.Name -in @("python.exe", "node.exe", "cmd.exe"))
    }

    foreach ($proc in $processes) {
        Stop-ProjectPid -ProcessId ([int]$proc.ProcessId) -ProjectRoot $ProjectRoot -Quiet:$Quiet
    }

    if (-not $Quiet) {
        Write-Ok "Project processes stopped."
    }
}
```

- [ ] **Step 2: Add status command**

Add:

```powershell
function Invoke-Status {
    param([string]$ProjectRoot)

    $pythonExe = Resolve-ProjectPython $ProjectRoot
    $runtime = Read-RuntimeState $ProjectRoot

    Write-Info "Project root: $ProjectRoot"
    if ($pythonExe) {
        Write-Ok "Python: $(& $pythonExe --version 2>&1) ($pythonExe)"
    }
    else {
        Write-Fail "Python: not found"
    }

    if (Test-CommandExists "node") {
        Write-Ok "Node.js: $(node --version)"
    }
    else {
        Write-WarnMsg "Node.js: not found"
    }

    if ($runtime) {
        Write-Info "Runtime metadata: $(Get-RuntimePath $ProjectRoot)"
        foreach ($name in @("backend", "frontend")) {
            $entry = $runtime.$name
            if ($entry -and $entry.pid) {
                $pid = [int]$entry.pid
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($proc -and (Test-ProjectProcess -ProcessId $pid -ProjectRoot $ProjectRoot)) {
                    Write-Ok "$name running: PID $pid, port $($entry.port)"
                }
                else {
                    Write-WarnMsg "$name metadata is stale: PID $pid"
                }
            }
        }
    }
    else {
        Write-WarnMsg "No runtime metadata found."
    }

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            Write-WarnMsg "Port $port is listening."
        }
        else {
            Write-Ok "Port $port is not listening."
        }
    }
}
```

- [ ] **Step 3: Verify start/status/stop**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start -NoBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 status
```

Expected:

```text
[OK]   Backend ready: http://127.0.0.1:8000
[OK]   Project processes stopped.
```

After stop, `status` should not show project-owned backend/frontend processes as running.

- [ ] **Step 4: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner stop and status"
```

## Task 7: Logs and Restart Commands

**Files:**

- Modify: `scripts/dev.ps1`

- [ ] **Step 1: Add logs command**

Add:

```powershell
function Invoke-Logs {
    param(
        [string]$ProjectRoot,
        [bool]$Follow = $false
    )

    $logsPath = Get-LogsPath $ProjectRoot
    $files = @(
        (Join-Path $logsPath "backend-start.log"),
        (Join-Path $logsPath "backend-start.err.log"),
        (Join-Path $logsPath "frontend-start.log"),
        (Join-Path $logsPath "frontend-start.err.log")
    )

    foreach ($file in $files) {
        Write-Info $file
        if (Test-Path $file) {
            Get-Content -LiteralPath $file -Tail 80
        }
        else {
            Write-WarnMsg "Missing log file."
        }
    }

    if ($Follow) {
        $existing = $files | Where-Object { Test-Path $_ }
        if ($existing.Count -gt 0) {
            Get-Content -LiteralPath $existing -Tail 20 -Wait
        }
    }
}
```

The existing `restart` branch in `Invoke-CommandByName` already calls `stop`, then `start`.

- [ ] **Step 2: Verify logs command**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 logs
```

Expected:

```text
[INFO] ...backend-start.log
[INFO] ...frontend-start.log
```

The command can report missing log files if the service has not been started yet.

- [ ] **Step 3: Verify restart command**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 restart -NoBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
```

Expected:

```text
[OK]   Backend ready: http://127.0.0.1:8000
[OK]   Frontend ready: http://localhost:3000
[OK]   Project processes stopped.
```

- [ ] **Step 4: Commit**

```powershell
git add scripts\dev.ps1
git commit -m "feat: add windows dev runner logs"
```

## Task 8: BAT Wrappers

**Files:**

- Create: `启动.bat`
- Create: `停止.bat`
- Create: `状态.bat`
- Create: `日志.bat`
- Modify: `安装依赖.bat`

- [ ] **Step 1: Add `启动.bat`**

```bat
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\dev.ps1" start
if errorlevel 1 pause
```

- [ ] **Step 2: Add `停止.bat`**

```bat
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\dev.ps1" stop
if errorlevel 1 pause
```

- [ ] **Step 3: Add `状态.bat`**

```bat
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\dev.ps1" status
pause
```

- [ ] **Step 4: Add `日志.bat`**

```bat
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\dev.ps1" logs
pause
```

- [ ] **Step 5: Simplify `安装依赖.bat`**

Use this final content:

```bat
@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%scripts\dev.ps1"

if not exist "%PS_SCRIPT%" (
    echo [ERROR] dev runner not found: %PS_SCRIPT%
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" install
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Dependency setup failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo [OK] Dependency setup completed successfully.
pause
```

- [ ] **Step 6: Verify wrappers parse**

Run:

```powershell
cmd /c 状态.bat
```

Expected:

```text
[INFO] Project root:
```

- [ ] **Step 7: Commit**

```powershell
git add 启动.bat 停止.bat 状态.bat 日志.bat 安装依赖.bat
git commit -m "feat: add windows dev runner wrappers"
```

## Task 9: README Update

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update startup documentation**

Add a Windows local runner section near the existing startup documentation:

````markdown
## Windows 本地启动管理

推荐在 Windows 上使用仓库内置启动器：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 install
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 start
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 status
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 logs
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
```

也可以双击：

- `安装依赖.bat`
- `启动.bat`
- `停止.bat`
- `状态.bat`
- `日志.bat`

启动器会统一选择 Python 环境，安装依赖到同一个环境，启动后端和前端，并把日志写入 `logs/`。运行状态保存在 `logs/runtime.json`，关闭时只停止本项目进程，避免误杀其他本地服务。
````

If README already has an overlapping section, replace the old startup-script description instead of duplicating it.

- [ ] **Step 2: Run Markdown formatting**

Run:

```powershell
npx --yes prettier --check README.md
```

If it fails, run:

```powershell
npx --yes prettier --write README.md
npx --yes prettier --check README.md
```

Expected:

```text
All matched files use Prettier code style!
```

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "docs: document windows dev runner"
```

## Task 10: Final Verification

**Files:**

- No code changes unless verification exposes a defect.

- [ ] **Step 1: Run doctor**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor
```

Expected:

```text
[OK]   Backend dependencies are healthy.
```

- [ ] **Step 2: Run backend tests**

```powershell
C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe -m pytest tests\test_system_auth.py tests\test_source_bindings.py tests\test_knowledge_scope.py tests\test_knowledge_base_scoping.py -q
```

Expected:

```text
19 passed
```

- [ ] **Step 3: Run frontend lint**

```powershell
cd frontend
npm run lint
cd ..
```

Expected:

```text
0 errors
```

Existing `ChatPanel.tsx` image warnings are acceptable.

- [ ] **Step 4: Run start/status/logs/stop smoke test**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start -NoBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 logs
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
```

Expected:

```text
[OK]   Backend ready: http://127.0.0.1:8000
[OK]   Frontend ready: http://localhost:3000
[OK]   Project processes stopped.
```

- [ ] **Step 5: Verify no runtime files are staged**

Run:

```powershell
git status --short
```

Expected:

```text
No staged logs/runtime.json, backend-start.log, frontend-start.log, node_modules, or cache files.
```

- [ ] **Step 6: Final code review**

Review:

- `scripts/dev.ps1` does not kill processes solely by port.
- `install` and `start` use the same Python selection logic.
- `start` writes runtime metadata only after both services are ready.
- `stop` verifies command lines before stopping PIDs.
- wrappers contain no duplicated process-management logic.

If no issues are found, proceed to the development-branch completion flow.
