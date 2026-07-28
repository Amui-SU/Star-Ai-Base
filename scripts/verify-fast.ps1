param(
    [string[]]$FrontendTest = @(),
    [string[]]$LintFile = @(),
    [string[]]$BackendTest = @()
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

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"

Set-Location $projectRoot

Invoke-Step "git diff --check" {
    git diff --check
}

if (
    $FrontendTest.Count -eq 0 -and
    $LintFile.Count -eq 0 -and
    $BackendTest.Count -eq 0
) {
    Write-Fail "Provide at least one targeted check: -FrontendTest, -LintFile, or -BackendTest."
    exit 2
}

if ($BackendTest.Count -gt 0) {
    Invoke-Step "targeted backend tests" {
        python -m pytest -q @BackendTest
    }
}

if ($FrontendTest.Count -gt 0 -or $LintFile.Count -gt 0) {
    Push-Location $frontendRoot
    try {
        if ($FrontendTest.Count -gt 0) {
            Invoke-Step "targeted frontend tests" {
                npm test -- --run @FrontendTest
            }
        }

        if ($LintFile.Count -gt 0) {
            Invoke-Step "targeted frontend lint" {
                npx eslint @LintFile
            }
        }
    }
    finally {
        Pop-Location
    }
}

Write-Ok "Fast verification complete"
