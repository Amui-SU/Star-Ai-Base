param(
    [switch]$SkipInstallDeps
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "[OK]   $msg" -ForegroundColor Green
}

function Write-WarnMsg($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Install-WithWinget($id, $displayName) {
    Write-Info "Installing $displayName via winget..."
    winget install --id $id --exact --accept-package-agreements --accept-source-agreements
}

function Test-CommandExists($commandName) {
    return [bool](Get-Command $commandName -ErrorAction SilentlyContinue)
}

function Test-FfmpegRunnable() {
    try {
        ffmpeg -version *> $null
        return $true
    }
    catch {
        return $false
    }
}

function Install-RequiredCommand($commandName, $displayName, $wingetId) {
    $alreadyInstalled = Test-CommandExists -commandName $commandName
    if ($commandName -eq "ffmpeg") {
        $alreadyInstalled = Test-FfmpegRunnable
    }

    if ($alreadyInstalled) {
        Write-Ok "$displayName already installed."
        return $true
    }

    Write-WarnMsg "$displayName not found."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-WarnMsg "winget is not available. Please install $displayName manually."
        return $false
    }

    try {
        Install-WithWinget -id $wingetId -displayName $displayName
    }
    catch {
        Write-WarnMsg "Failed to install $displayName automatically: $($_.Exception.Message)"
    }

    $installedNow = Test-CommandExists -commandName $commandName
    if ($commandName -eq "ffmpeg") {
        $installedNow = Test-FfmpegRunnable
    }

    if ($installedNow) {
        Write-Ok "$displayName is now available."
        return $true
    }

    Write-WarnMsg "$displayName is still unavailable. Please install it manually."
    return $false
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendPath = Join-Path $projectRoot "frontend"
$requirementsPath = Join-Path $projectRoot "requirements.txt"

Write-Info "Project root: $projectRoot"

Install-RequiredCommand -commandName "python" -displayName "Python" -wingetId "Python.Python.3.11" | Out-Null
Install-RequiredCommand -commandName "node" -displayName "Node.js LTS" -wingetId "OpenJS.NodeJS.LTS" | Out-Null
Install-RequiredCommand -commandName "ffmpeg" -displayName "ffmpeg" -wingetId "Gyan.FFmpeg" | Out-Null

$pythonReady = Test-CommandExists -commandName "python"
$nodeReady = Test-CommandExists -commandName "node"
$ffmpegReady = Test-FfmpegRunnable

if (-not $pythonReady) {
    throw "Python is required but not available."
}

if (-not $nodeReady) {
    throw "Node.js is required but not available."
}

$pythonVersion = python --version 2>&1
$nodeVersion = node --version 2>&1
$npmVersion = npm --version 2>&1

Write-Ok "Python: $pythonVersion"
Write-Ok "Node.js: $nodeVersion"
Write-Ok "npm: $npmVersion"
if ($ffmpegReady) {
    $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Ok "ffmpeg: $ffmpegVersion"
}
else {
    Write-WarnMsg "ffmpeg is missing. ASR local fallback may not work until ffmpeg is installed."
}

if ($SkipInstallDeps) {
    Write-Info "SkipInstallDeps enabled, dependency installation skipped."
    exit 0
}

if (-not (Test-Path $requirementsPath)) {
    throw "Missing requirements file: $requirementsPath"
}

if (-not (Test-Path $frontendPath)) {
    throw "Missing frontend directory: $frontendPath"
}

Write-Info "Upgrading pip..."
python -m pip install --upgrade pip

Write-Info "Installing backend dependencies from requirements.txt..."
python -m pip install -r $requirementsPath

Write-Info "Installing frontend dependencies..."
Push-Location $frontendPath
try {
    npm install
}
finally {
    Pop-Location
}

Write-Ok "All checks and installations completed."
