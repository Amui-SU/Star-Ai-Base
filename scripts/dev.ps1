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

function Invoke-Doctor {
    param([string]$ProjectRoot)
    Write-WarnMsg "doctor command is not implemented yet."
    throw "doctor command is not implemented yet."
}

function Invoke-Install {
    param(
        [string]$ProjectRoot,
        [switch]$SkipFrontend
    )
    Write-WarnMsg "install command is not implemented yet."
    throw "install command is not implemented yet."
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
