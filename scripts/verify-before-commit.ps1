param(
    [switch]$Format,
    [switch]$SkipFrontendBuild,
    [switch]$SkipFrontendTests,
    [switch]$SkipBackendTests
)

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Fail($Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )

    Write-Info $Name
    & $Script
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "$Name failed"
        exit $LASTEXITCODE
    }
    Write-Ok $Name
}

function Get-ProjectRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Get-ChangedFiles {
    $files = @()
    $files += git diff --name-only --diff-filter=ACMRT
    $files += git diff --cached --name-only --diff-filter=ACMRT
    return $files | Where-Object { $_ } | Sort-Object -Unique
}

function Select-ExistingFiles {
    param([string[]]$Paths)

    $root = Get-ProjectRoot
    return @(
        $Paths |
            ForEach-Object { Join-Path $root $_ } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
}

function Get-RelativePath {
    param(
        [string]$BasePath,
        [string]$TargetPath
    )

    $baseUri = [System.Uri]((Resolve-Path -LiteralPath $BasePath).Path.TrimEnd("\") + "\")
    $targetUri = [System.Uri](Resolve-Path -LiteralPath $TargetPath).Path
    return [System.Uri]::UnescapeDataString(
        $baseUri.MakeRelativeUri($targetUri).ToString()
    ).Replace("/", "\")
}

$projectRoot = Get-ProjectRoot
$frontendRoot = Join-Path $projectRoot "frontend"
Set-Location $projectRoot

$changedFiles = @(Get-ChangedFiles)
$pythonFiles = @($changedFiles | Where-Object { $_ -match "\.py$" })
$webFiles = @(
    $changedFiles |
        Where-Object { $_ -match "\.(js|ts|jsx|tsx|json|css|scss|less|html|md|yaml|yml)$" }
)

Invoke-Step "git diff --check" {
    git diff --check
}

if ($pythonFiles.Count -gt 0) {
    $existingPythonFiles = Select-ExistingFiles $pythonFiles
    if ($existingPythonFiles.Count -gt 0) {
        if ($Format) {
            Invoke-Step "black format changed Python files" {
                black @existingPythonFiles
            }
        }
        Invoke-Step "black check changed Python files" {
            black --check @existingPythonFiles
        }
    }
}

if (-not $SkipBackendTests) {
    Invoke-Step "backend tests" {
        python -m pytest -q
    }
}

if ($webFiles.Count -gt 0) {
    $existingWebFiles = Select-ExistingFiles $webFiles
    if ($existingWebFiles.Count -gt 0) {
        Push-Location $frontendRoot
        try {
            $relativeWebFiles = @(
                $existingWebFiles |
                    ForEach-Object {
                        Get-RelativePath -BasePath $frontendRoot -TargetPath $_
                    }
            )

            if ($Format) {
                Invoke-Step "prettier format changed frontend/docs files" {
                    npx prettier --write @relativeWebFiles
                }
            }
            Invoke-Step "prettier check changed frontend/docs files" {
                npx prettier --check @relativeWebFiles
            }
        }
        finally {
            Pop-Location
        }
    }
}

Push-Location $frontendRoot
try {
    Invoke-Step "frontend lint" {
        npm run lint
    }

    if (-not $SkipFrontendTests) {
        Invoke-Step "frontend tests" {
            npm test
        }
    }

    if (-not $SkipFrontendBuild) {
        Invoke-Step "frontend build" {
            npm run build
        }
    }
}
finally {
    Pop-Location
}

Invoke-Step "git diff --cached --check" {
    git diff --cached --check
}

Write-Ok "commit verification complete"
