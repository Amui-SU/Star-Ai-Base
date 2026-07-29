[CmdletBinding(PositionalBinding = $false)]
param(
    [string[]]$FrontendTest = @(),
    [string[]]$LintFile = @(),
    [string[]]$BackendTest = @(),
    [string[]]$StaticFile = @()
)

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Fail($Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Expand-Targets {
    param([string[]]$Targets)

    $expanded = @()
    foreach ($target in $Targets) {
        if ($null -eq $target) {
            continue
        }

        foreach ($part in $target -split ",") {
            $trimmed = $part.Trim()
            if ($trimmed.Length -gt 0) {
                $expanded += $trimmed
            }
        }
    }

    return $expanded
}

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

$FrontendTest = @(Expand-Targets $FrontendTest)
$LintFile = @(Expand-Targets $LintFile)
$BackendTest = @(Expand-Targets $BackendTest)
$StaticFile = @(Expand-Targets $StaticFile)

if (
    $FrontendTest.Count -eq 0 -and
    $LintFile.Count -eq 0 -and
    $BackendTest.Count -eq 0 -and
    $StaticFile.Count -eq 0
) {
    Write-Fail "Provide at least one targeted check: -FrontendTest, -LintFile, -BackendTest, or -StaticFile."
    exit 2
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"
$projectRootPrefix = $projectRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
$allowedStaticExtensions = @(".md", ".txt", ".css", ".scss", ".less", ".html", ".json", ".yaml", ".yml")

foreach ($staticTarget in $StaticFile) {
    if ([System.IO.Path]::IsPathRooted($staticTarget)) {
        Write-Fail "Static file must be relative to project root: $staticTarget"
        exit 2
    }

    $candidate = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $staticTarget))
    if (-not $candidate.StartsWith($projectRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Fail "Static file must stay within project root: $staticTarget"
        exit 2
    }

    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        Write-Fail "Static file not found: $staticTarget"
        exit 2
    }

    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($projectRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Fail "Static file must stay within project root: $staticTarget"
        exit 2
    }

    if ($allowedStaticExtensions -notcontains [System.IO.Path]::GetExtension($resolved).ToLowerInvariant()) {
        Write-Fail "Unsupported static file: $staticTarget"
        exit 2
    }
}

Set-Location $projectRoot

Invoke-Step "git diff --check" {
    git diff --check
}

if ($BackendTest.Count -gt 0) {
    Invoke-Step "targeted backend tests" {
        python -m pytest -q @BackendTest
    }
}

if ($FrontendTest.Count -gt 0 -or $LintFile.Count -gt 0) {
    Push-Location $frontendRoot
    try {
        $binSuffix = if ($env:OS -eq "Windows_NT") { ".cmd" } else { "" }
        $vitest = Join-Path $frontendRoot "node_modules/.bin/vitest$binSuffix"
        $eslint = Join-Path $frontendRoot "node_modules/.bin/eslint$binSuffix"

        if ($FrontendTest.Count -gt 0) {
            if (-not (Test-Path -LiteralPath $vitest -PathType Leaf)) {
                Write-Fail "Missing frontend dependency: $vitest"
                exit 1
            }

            Invoke-Step "targeted frontend tests" {
                & $vitest run @FrontendTest
            }
        }

        if ($LintFile.Count -gt 0) {
            if (-not (Test-Path -LiteralPath $eslint -PathType Leaf)) {
                Write-Fail "Missing frontend dependency: $eslint"
                exit 1
            }

            Invoke-Step "targeted frontend lint" {
                & $eslint @LintFile
            }
        }
    }
    finally {
        Pop-Location
    }
}

Write-Ok "Fast verification complete"
