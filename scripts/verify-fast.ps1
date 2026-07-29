[CmdletBinding(PositionalBinding = $false)]
param(
    [string[]]$FrontendTest = @(),
    [string[]]$LintFile = @(),
    [string[]]$BackendTest = @(),
    [string[]]$StaticFile = @(),
    [string[]]$TaskFile = @()
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

function Get-GitNullSeparatedPaths {
    param(
        [string]$Arguments,
        [string]$Description
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.Arguments = $Arguments
    $startInfo.WorkingDirectory = $projectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            Write-Fail "Could not start git to enumerate $Description"
            exit 1
        }

        $stderrTask = $process.StandardError.ReadToEndAsync()
        $paths = New-Object "System.Collections.Generic.List[string]"
        $pathBytes = New-Object "System.Collections.Generic.List[byte]"
        $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
        [byte[]]$buffer = New-Object byte[] 4096
        $stdout = $process.StandardOutput.BaseStream
        $pathDecodeFailed = $false

        while (($bytesRead = $stdout.Read($buffer, 0, $buffer.Length)) -gt 0) {
            for ($index = 0; $index -lt $bytesRead; $index++) {
                if ($buffer[$index] -eq 0) {
                    try {
                        $path = $utf8.GetString($pathBytes.ToArray())
                        if ($path.Length -gt 0) {
                            [void]$paths.Add($path)
                        }
                    }
                    catch [System.Text.DecoderFallbackException] {
                        $pathDecodeFailed = $true
                    }
                    $pathBytes.Clear()
                }
                else {
                    [void]$pathBytes.Add($buffer[$index])
                }
            }
        }

        $process.WaitForExit()
        $stderr = $stderrTask.Result
        $exitCode = $process.ExitCode

        if ($exitCode -ne 0) {
            $detail = $stderr.Trim()
            if ($detail.Length -gt 0) {
                Write-Fail "Could not enumerate ${Description}: $detail"
            }
            else {
                Write-Fail "Could not enumerate $Description"
            }
            exit $exitCode
        }

        if ($pathDecodeFailed -or $pathBytes.Count -ne 0) {
            Write-Fail "Git returned an invalid UTF-8 path while enumerating $Description"
            exit 1
        }

        return $paths.ToArray()
    }
    catch {
        Write-Fail "Could not enumerate ${Description}: $($_.Exception.Message)"
        exit 1
    }
    finally {
        $process.Dispose()
    }
}

function Get-UntrackedFiles {
    return @(
        Get-GitNullSeparatedPaths `
            "ls-files -z --others --exclude-standard" `
            "untracked files"
    )
}

function Get-ChangedFiles {
    $paths = @()
    $paths += Get-GitNullSeparatedPaths "diff --name-only -z" "unstaged changes"
    $paths += Get-GitNullSeparatedPaths "diff --cached --name-only -z" "staged changes"
    $paths += Get-UntrackedFiles
    return @($paths | Where-Object { $_ } | Sort-Object -Unique)
}

function Test-FileContainsNul {
    param([string]$Path)

    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    try {
        [byte[]]$buffer = New-Object byte[] 65536
        while (($bytesRead = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            for ($index = 0; $index -lt $bytesRead; $index++) {
                if ($buffer[$index] -eq 0) {
                    return $true
                }
            }
        }
        return $false
    }
    finally {
        $stream.Dispose()
    }
}

function Get-UntrackedTextViolation {
    param(
        [string]$Path,
        [string]$RelativePath
    )

    $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
    $reader = $null
    try {
        $reader = [System.IO.StreamReader]::new($Path, $strictUtf8, $true)
        $lineNumber = 0
        $hasLine = $false
        $lastLine = $null
        $firstViolation = $null

        while (($line = $reader.ReadLine()) -ne $null) {
            $lineNumber++
            $hasLine = $true
            $lastLine = $line

            if ($null -eq $firstViolation -and $line -match "[ \t]$") {
                $firstViolation = "${RelativePath}:$lineNumber trailing whitespace"
            }

            if (
                $null -eq $firstViolation -and
                $line -match "^(<{7,}|={7,}|>{7,}|\|{7,})( .*)?$"
            ) {
                $firstViolation = "${RelativePath}:$lineNumber unresolved conflict marker"
            }
        }

        if (
            $null -eq $firstViolation -and
            $hasLine -and
            $lastLine -match "^[ \t]*$"
        ) {
            $firstViolation = "${RelativePath}:$lineNumber terminal blank line"
        }

        return $firstViolation
    }
    catch [System.Text.DecoderFallbackException] {
        Write-Info "Skipping non-UTF-8 untracked file: $RelativePath"
        return $null
    }
    catch {
        Write-Fail "Could not read untracked file: $RelativePath"
        exit 1
    }
    finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }
    }
}

function Test-UntrackedTextFiles {
    param(
        [string[]]$Files = @(),
        [switch]$Scoped
    )

    Write-Info "untracked text hygiene"
    $untrackedFiles = if ($Scoped) { @($Files) } else { @(Get-UntrackedFiles) }

    foreach ($relativePath in $untrackedFiles) {
        $candidate = Join-Path $projectRoot $relativePath
        try {
            $item = Get-Item -LiteralPath $candidate -Force
        }
        catch {
            Write-Fail "Could not inspect untracked file: $relativePath"
            exit 1
        }

        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            Write-Fail "Untracked file is a symbolic link or reparse point: $relativePath"
            exit 1
        }

        try {
            if (Test-FileContainsNul $candidate) {
                continue
            }
        }
        catch {
            Write-Fail "Could not read untracked file: $relativePath"
            exit 1
        }

        $violation = Get-UntrackedTextViolation $candidate $relativePath
        if ($null -ne $violation) {
            Write-Fail "Untracked text check failed: $violation"
            exit 1
        }
    }

    Write-Ok "untracked text hygiene"
}

$FrontendTest = @(Expand-Targets $FrontendTest)
$LintFile = @(Expand-Targets $LintFile)
$BackendTest = @(Expand-Targets $BackendTest)
$StaticFile = @(Expand-Targets $StaticFile)
$TaskFile = @(Expand-Targets $TaskFile)

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
$frontendRootPrefix = $frontendRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
$pathComparison = if ($env:OS -eq "Windows_NT") {
    [System.StringComparison]::OrdinalIgnoreCase
} else {
    [System.StringComparison]::Ordinal
}
$pathComparer = if ($env:OS -eq "Windows_NT") {
    [System.StringComparer]::OrdinalIgnoreCase
} else {
    [System.StringComparer]::Ordinal
}
$allowedStaticExtensions = @(".md", ".txt", ".css", ".scss", ".less")
$changedFiles = @(Get-ChangedFiles)
$changedPathSet = [System.Collections.Generic.HashSet[string]]::new($pathComparer)
foreach ($changedFile in $changedFiles) {
    [void]$changedPathSet.Add($changedFile.Replace("\", "/"))
}
$staticTargetSet = [System.Collections.Generic.HashSet[string]]::new($pathComparer)
$lintTargetSet = [System.Collections.Generic.HashSet[string]]::new($pathComparer)
$taskFileSet = [System.Collections.Generic.HashSet[string]]::new($pathComparer)
$taskFilesNormalized = New-Object "System.Collections.Generic.List[string]"

foreach ($taskTarget in $TaskFile) {
    if ([System.IO.Path]::IsPathRooted($taskTarget)) {
        Write-Fail "Task file must be relative to project root: $taskTarget"
        exit 2
    }

    try {
        $taskPathForHost = $taskTarget.Replace("\", "/").Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $taskPathForHost))
    }
    catch {
        Write-Fail "Invalid task file path: $taskTarget"
        exit 2
    }

    if (-not $candidate.StartsWith($projectRootPrefix, $pathComparison)) {
        Write-Fail "Task file must stay within project root: $taskTarget"
        exit 2
    }

    $relativeTaskPath = $candidate.Substring($projectRootPrefix.Length).Replace("\", "/")
    if (-not $taskFileSet.Add($relativeTaskPath)) {
        Write-Fail "Duplicate task file: $taskTarget"
        exit 2
    }
    if (-not $changedPathSet.Contains($relativeTaskPath)) {
        Write-Fail "Task file is not changed: $taskTarget"
        exit 2
    }
    [void]$taskFilesNormalized.Add($relativeTaskPath)
}

$taskScopeEnabled = $taskFilesNormalized.Count -gt 0
$verificationFiles = @()
if ($taskScopeEnabled) {
    $verificationFiles = @($taskFilesNormalized.ToArray())
}
else {
    $verificationFiles = @($changedFiles)
}

foreach ($lintTarget in $LintFile) {
    if ([System.IO.Path]::IsPathRooted($lintTarget)) {
        Write-Fail "Lint file must be relative to frontend root: $lintTarget"
        exit 2
    }

    try {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $frontendRoot $lintTarget))
    }
    catch {
        Write-Fail "Invalid lint file path: $lintTarget"
        exit 2
    }

    if (-not $candidate.StartsWith($frontendRootPrefix, $pathComparison)) {
        Write-Fail "Lint file must stay within frontend root: $lintTarget"
        exit 2
    }

    $relativeLintPath = $candidate.Substring($frontendRootPrefix.Length).Replace("\", "/")
    [void]$lintTargetSet.Add($relativeLintPath)
}

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
        Write-Fail "Unsupported static file: $staticTarget; use full verification."
        exit 2
    }

    $relativeStaticPath = $candidate.Substring($projectRootPrefix.Length).Replace("\", "/")
    [void]$staticTargetSet.Add($relativeStaticPath)
}

Set-Location $projectRoot

if ($taskScopeEnabled) {
    Invoke-Step "git diff --check (task files)" {
        git diff --check -- @verificationFiles
    }

    Invoke-Step "git diff --cached --check (task files)" {
        git diff --cached --check -- @verificationFiles
    }

    $untrackedPathSet = [System.Collections.Generic.HashSet[string]]::new($pathComparer)
    foreach ($untrackedFile in @(Get-UntrackedFiles)) {
        [void]$untrackedPathSet.Add($untrackedFile.Replace("\", "/"))
    }
    $scopedUntrackedFiles = @(
        $verificationFiles | Where-Object { $untrackedPathSet.Contains($_) }
    )
    Test-UntrackedTextFiles -Files $scopedUntrackedFiles -Scoped
}
else {
    Invoke-Step "git diff --check" {
        git diff --check
    }

    Invoke-Step "git diff --cached --check" {
        git diff --cached --check
    }

    Test-UntrackedTextFiles
}

foreach ($staticTarget in $staticTargetSet) {
    if (-not $changedPathSet.Contains($staticTarget)) {
        Write-Fail "Static file target is not changed: $staticTarget"
        exit 2
    }
}

foreach ($changedFile in $verificationFiles) {
    $normalizedChangedFile = $changedFile.Replace("\", "/")
    $extension = [System.IO.Path]::GetExtension($normalizedChangedFile).ToLowerInvariant()

    if ($allowedStaticExtensions -contains $extension) {
        if (-not $staticTargetSet.Contains($normalizedChangedFile)) {
            Write-Fail "Missing -StaticFile target for changed file: $changedFile"
            exit 2
        }
        continue
    }

    if ($extension -eq ".py") {
        if ($BackendTest.Count -eq 0) {
            Write-Fail "Changed Python files require at least one -BackendTest target: $changedFile"
            exit 2
        }
        continue
    }

    $frontendCodeExtensions = @(".js", ".jsx", ".ts", ".tsx")
    if (
        $normalizedChangedFile.StartsWith("frontend/", $pathComparison) -and
        $frontendCodeExtensions -contains $extension
    ) {
        $relativeFrontendPath = $normalizedChangedFile.Substring("frontend/".Length)
        if (-not $lintTargetSet.Contains($relativeFrontendPath)) {
            Write-Fail "Missing -LintFile target for changed frontend file: $relativeFrontendPath"
            exit 2
        }
        continue
    }

    Write-Fail "Fast verification does not support changed file: $changedFile; use full verification."
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
