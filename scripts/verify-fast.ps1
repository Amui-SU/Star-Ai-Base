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

function Test-StaticPathHasReparsePoint {
    param(
        [string]$Path,
        [string]$ProjectRoot,
        [string]$ProjectRootPrefix
    )

    $current = $ProjectRoot
    $item = Get-Item -LiteralPath $current -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        return $true
    }

    $relativePath = $Path.Substring($ProjectRootPrefix.Length)
    foreach ($segment in $relativePath.Split([char[]]@('\', '/'), [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $current = Join-Path $current $segment
        $item = Get-Item -LiteralPath $current -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            return $true
        }
    }

    return $false
}

function Test-UntrackedTextFiles {
    Write-Info "untracked text hygiene"
    $untrackedFiles = @(git ls-files --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Could not enumerate untracked files"
        exit $LASTEXITCODE
    }

    foreach ($relativePath in $untrackedFiles) {
        $candidate = Join-Path $projectRoot $relativePath
        try {
            [byte[]]$bytes = [System.IO.File]::ReadAllBytes($candidate)
        }
        catch {
            Write-Fail "Could not read untracked file: $relativePath"
            exit 1
        }

        if ($bytes -contains [byte]0) {
            continue
        }

        [string]$content = [System.Text.Encoding]::UTF8.GetString($bytes)
        [string[]]$lines = @($content -split "\r\n|\n|\r")
        for ($index = 0; $index -lt $lines.Count; $index++) {
            $line = $lines[$index]
            $lineNumber = $index + 1

            if ($line -match "[ \t]$") {
                Write-Fail "Untracked text check failed: ${relativePath}:$lineNumber trailing whitespace"
                exit 1
            }

            if ($line -match "^(<{7}( .*)?|={7}|>{7}( .*)?)$") {
                Write-Fail "Untracked text check failed: ${relativePath}:$lineNumber unresolved conflict marker"
                exit 1
            }
        }

        $lineEndingLength = if ($content.EndsWith("`r`n")) {
            2
        }
        elseif ($content.EndsWith("`n") -or $content.EndsWith("`r")) {
            1
        }
        else {
            0
        }

        if ($lineEndingLength -gt 0) {
            $beforeLastLineEnding = $content.Substring(0, $content.Length - $lineEndingLength)
            if (
                $beforeLastLineEnding.EndsWith("`r`n") -or
                $beforeLastLineEnding.EndsWith("`n") -or
                $beforeLastLineEnding.EndsWith("`r")
            ) {
                $lineNumber = [System.Text.RegularExpressions.Regex]::Matches(
                    $beforeLastLineEnding,
                    "\r\n|\n|\r"
                ).Count + 1
                Write-Fail "Untracked text check failed: ${relativePath}:$lineNumber terminal blank line"
                exit 1
            }
        }
    }

    Write-Ok "untracked text hygiene"
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
$pathComparison = if ($env:OS -eq "Windows_NT") {
    [System.StringComparison]::OrdinalIgnoreCase
} else {
    [System.StringComparison]::Ordinal
}
$allowedStaticExtensions = @(".md", ".txt", ".css", ".scss", ".less", ".html", ".json", ".yaml", ".yml")

foreach ($staticTarget in $StaticFile) {
    if ([System.IO.Path]::IsPathRooted($staticTarget)) {
        Write-Fail "Static file must be relative to project root: $staticTarget"
        exit 2
    }

    try {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $staticTarget))
    }
    catch {
        Write-Fail "Invalid static file path: $staticTarget"
        exit 2
    }

    if (-not $candidate.StartsWith($projectRootPrefix, $pathComparison)) {
        Write-Fail "Static file must stay within project root: $staticTarget"
        exit 2
    }

    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        Write-Fail "Static file not found: $staticTarget"
        exit 2
    }

    if (Test-StaticPathHasReparsePoint $candidate $projectRoot $projectRootPrefix) {
        Write-Fail "Static file path cannot contain a symbolic link: $staticTarget"
        exit 2
    }

    try {
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
    }
    catch {
        Write-Fail "Invalid static file path: $staticTarget"
        exit 2
    }

    if (-not $resolved.StartsWith($projectRootPrefix, $pathComparison)) {
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

Invoke-Step "git diff --cached --check" {
    git diff --cached --check
}

Test-UntrackedTextFiles

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
