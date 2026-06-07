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
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
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
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        [System.IO.Directory]::CreateDirectory($Path) | Out-Null
    }
}

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

    foreach ($target in @("Process", "User", "Machine")) {
        $envPython = [Environment]::GetEnvironmentVariable("BILIBILI_RAG_PYTHON", $target)
        if ($envPython) {
            $candidates += $envPython
        }
    }

    $candidates += "C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe"
    if (Test-CommandExists "python") {
        $candidates += "python"
    }

    foreach ($candidate in $candidates) {
        if (($candidate -eq "python" -or (Test-Path -LiteralPath $candidate -PathType Leaf)) -and (Test-PythonRunnable $candidate)) {
            return $candidate
        }
    }

    return $null
}

function Test-BackendDependencies {
    param([string]$PythonExe)

    $code = "import fastapi, uvicorn, cryptography, jose; from passlib.context import CryptContext; CryptContext(schemes=['bcrypt'], deprecated='auto').hash('dependency-check')"
    try {
        & $PythonExe -c $code *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-FfmpegRunnable {
    try {
        if (-not (Test-CommandExists "ffmpeg")) {
            return $false
        }

        ffmpeg -version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)

    try {
        $result = netstat -ano | Select-String ":$Port\s+.*LISTENING"
        return [bool]$result
    }
    catch {
        return $false
    }
}

function Invoke-Doctor {
    param([string]$ProjectRoot)

    $failed = $false
    $frontendPath = Get-FrontendPath $ProjectRoot
    $logsPath = Get-LogsPath $ProjectRoot
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    Write-Info "Project root: $ProjectRoot"

    if (Test-Path -LiteralPath $ProjectRoot -PathType Container) {
        Write-Ok "Project root exists."
    }
    else {
        $failed = $true
        Write-Fail "Project root missing."
        throw "doctor found failed checks."
    }

    if (Test-Path -LiteralPath $frontendPath -PathType Container) {
        Write-Ok "Frontend directory exists."
    }
    else {
        $failed = $true
        Write-Fail "Frontend directory missing: $frontendPath"
    }

    if ($pythonExe) {
        $pythonVersion = & $pythonExe --version 2>&1
        Write-Ok "Python: $pythonVersion ($pythonExe)"
        if (Test-BackendDependencies $pythonExe) {
            Write-Ok "Backend dependencies are healthy."
        }
        else {
            $failed = $true
            Write-Fail "Backend dependencies are incomplete. Run: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 install"
        }
    }
    else {
        $failed = $true
        Write-Fail "No runnable Python found. Install Python or set BILIBILI_RAG_PYTHON."
    }

    if (Test-CommandExists "node") {
        Write-Ok "Node.js: $(node --version)"
    }
    else {
        $failed = $true
        Write-Fail "Node.js is missing."
    }

    if (Test-CommandExists "npm") {
        Write-Ok "npm: $(npm --version)"
    }
    else {
        $failed = $true
        Write-Fail "npm is missing."
    }

    if (Test-Path -LiteralPath (Join-Path $frontendPath "node_modules") -PathType Container) {
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

    try {
        Ensure-Directory $logsPath
        $probePath = Join-Path $logsPath ".doctor-write-test"
        Set-Content -LiteralPath $probePath -Value "ok" -Encoding ASCII
        Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
        Write-Ok "Logs directory is writable: $logsPath"
    }
    catch {
        $failed = $true
        Write-Fail "Logs directory is not writable: $logsPath"
    }

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            Write-WarnMsg "Port $port is already listening. Run status to inspect ownership."
        }
        else {
            Write-Ok "Port $port is free."
        }
    }

    if ($failed) {
        throw "doctor found failed checks."
    }
}

function Invoke-Install {
    param(
        [string]$ProjectRoot,
        [switch]$SkipFrontend
    )

    $frontendPath = Get-FrontendPath $ProjectRoot
    $requirementsPath = Join-Path $ProjectRoot "requirements.txt"
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    if (-not $pythonExe) {
        throw "No runnable Python found. Install Python or set BILIBILI_RAG_PYTHON."
    }
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        throw "Missing requirements file: $requirementsPath"
    }
    if (-not (Test-Path -LiteralPath $frontendPath -PathType Container)) {
        throw "Missing frontend directory: $frontendPath"
    }

    Write-Ok "Using Python: $(& $pythonExe --version 2>&1) ($pythonExe)"
    Write-Info "Upgrading pip..."
    & $pythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }

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
        Push-Location -LiteralPath $frontendPath
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

function Invoke-Start {
    param(
        [string]$ProjectRoot,
        [switch]$NoBrowser
    )
    Write-WarnMsg "start command is not implemented yet."
    throw "start command is not implemented yet."
}

function Invoke-Stop {
    param([string]$ProjectRoot)
    Write-WarnMsg "stop command is not implemented yet."
    throw "stop command is not implemented yet."
}

function Invoke-Status {
    param([string]$ProjectRoot)
    Write-WarnMsg "status command is not implemented yet."
    throw "status command is not implemented yet."
}

function Invoke-Logs {
    param(
        [string]$ProjectRoot,
        [switch]$Follow
    )
    Write-WarnMsg "logs command is not implemented yet."
    throw "logs command is not implemented yet."
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
        default { throw "Unknown command: $Command" }
    }
}

Invoke-CommandByName -Command $Command
