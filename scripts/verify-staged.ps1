[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Fail($Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Invoke-NativeStep {
    param(
        [string]$Name,
        [scriptblock]$Script
    )

    Write-Info $Name
    & $Script
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Fail "$Name failed"
        exit $exitCode
    }
    Write-Ok $Name
}

function Get-StagedPaths {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.Arguments = "diff --cached --name-only -z --diff-filter=ACMR"
    $startInfo.WorkingDirectory = $projectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            Write-Fail "Could not start Git to enumerate staged files"
            exit 1
        }

        $stderrTask = $process.StandardError.ReadToEndAsync()
        $paths = New-Object "System.Collections.Generic.List[string]"
        $pathBytes = New-Object "System.Collections.Generic.List[byte]"
        $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
        [byte[]]$buffer = New-Object byte[] 4096
        $stdout = $process.StandardOutput.BaseStream
        $decodeFailed = $false

        while (($bytesRead = $stdout.Read($buffer, 0, $buffer.Length)) -gt 0) {
            for ($index = 0; $index -lt $bytesRead; $index++) {
                if ($buffer[$index] -eq 0) {
                    try {
                        $path = $strictUtf8.GetString($pathBytes.ToArray())
                        if ($path.Length -eq 0) {
                            $decodeFailed = $true
                        }
                        else {
                            [void]$paths.Add($path)
                        }
                    }
                    catch [System.Text.DecoderFallbackException] {
                        $decodeFailed = $true
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
                Write-Fail "Could not enumerate staged files: $detail"
            }
            else {
                Write-Fail "Could not enumerate staged files"
            }
            exit $exitCode
        }
        if ($decodeFailed -or $pathBytes.Count -ne 0) {
            Write-Fail "Git returned an invalid UTF-8 staged path"
            exit 1
        }

        return $paths.ToArray()
    }
    catch {
        Write-Fail "Could not enumerate staged files: $($_.Exception.Message)"
        exit 1
    }
    finally {
        $process.Dispose()
    }
}

function Test-PathHasReparsePoint {
    param([string]$Path)

    $current = $projectRoot
    $item = Get-Item -LiteralPath $current -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        return $true
    }

    $relativePath = $Path.Substring($projectRootPrefix.Length)
    foreach ($segment in $relativePath.Split(
        [char[]]@('\', '/'),
        [System.StringSplitOptions]::RemoveEmptyEntries
    )) {
        $current = Join-Path $current $segment
        $item = Get-Item -LiteralPath $current -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            return $true
        }
    }
    return $false
}

function Test-GitIndexSymbolicLink {
    param([string]$RelativePath)

    $entries = @(git -C $projectRoot --literal-pathspecs ls-files -s -- $RelativePath)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Fail "Could not inspect Git index mode for staged file: $RelativePath"
        exit $exitCode
    }
    return @($entries | Where-Object { $_ -match "^120000 " }).Count -gt 0
}

function Resolve-StagedFile {
    param([string]$RelativePath)

    if ($RelativePath.Length -eq 0) {
        Write-Fail "Staged path must not be empty"
        exit 1
    }
    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        Write-Fail "Staged path must be repository-relative: $RelativePath"
        exit 1
    }
    if (@($RelativePath -split "[\\/]" | Where-Object { $_ -eq ".." }).Count -gt 0) {
        Write-Fail "Staged path must not contain traversal segments: $RelativePath"
        exit 1
    }

    try {
        $hostPath = $RelativePath.Replace(
            "/",
            [System.IO.Path]::DirectorySeparatorChar
        )
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $hostPath))
    }
    catch {
        Write-Fail "Invalid staged path: $RelativePath"
        exit 1
    }

    if (-not $candidate.StartsWith($projectRootPrefix, $pathComparison)) {
        Write-Fail "Staged path must stay within the repository: $RelativePath"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        Write-Fail "Staged file is missing or is not a regular file: $RelativePath"
        exit 1
    }
    if (Test-PathHasReparsePoint $candidate) {
        Write-Fail "Staged file cannot be a symbolic link or reparse point: $RelativePath"
        exit 1
    }
    if (Test-GitIndexSymbolicLink $RelativePath) {
        Write-Fail "Staged file cannot use Git symbolic link mode 120000: $RelativePath"
        exit 1
    }

    try {
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
    }
    catch {
        Write-Fail "Could not resolve staged file: $RelativePath"
        exit 1
    }
    if (-not $resolved.StartsWith($projectRootPrefix, $pathComparison)) {
        Write-Fail "Resolved staged path must stay within the repository: $RelativePath"
        exit 1
    }

    git -C $projectRoot --literal-pathspecs diff --quiet -- $RelativePath
    $diffExitCode = $LASTEXITCODE
    if ($diffExitCode -eq 1) {
        Write-Fail (
            "Staged file also has unstaged changes: $RelativePath. " +
            "Stage the working-tree version before verification."
        )
        exit 1
    }
    if ($diffExitCode -ne 0) {
        Write-Fail "Could not compare staged and working-tree content: $RelativePath"
        exit $diffExitCode
    }

    return [pscustomobject]@{
        RelativePath = $RelativePath
        FullPath = $resolved
    }
}

function Confirm-PythonFormatterDependencies {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        Write-Fail (
            "Missing Python executable. Install Python 3, ensure python is on PATH, " +
            "then run: python -m pip install black"
        )
        exit 1
    }

    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        python --version > $null 2>&1
        $pythonExitCode = $LASTEXITCODE
        python -c "import black" > $null 2>&1
        $blackExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }

    if ($pythonExitCode -ne 0) {
        Write-Fail (
            "Python is unavailable or could not start. Install Python 3, ensure python " +
            "is on PATH, then run: python -m pip install black"
        )
        exit 1
    }

    if ($blackExitCode -ne 0) {
        Write-Fail (
            "Missing Python formatter dependency: Black. " +
            "Prepare it with: python -m pip install black"
        )
        exit 1
    }
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"
$projectRootPrefix = $projectRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
$isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows
)
$pathComparison = if ($isWindows) {
    [System.StringComparison]::OrdinalIgnoreCase
}
else {
    [System.StringComparison]::Ordinal
}
$webExtensions = @(
    ".js", ".ts", ".jsx", ".tsx", ".json", ".css", ".scss", ".less",
    ".html", ".md", ".yaml", ".yml"
)

Set-Location $projectRoot

Invoke-NativeStep "git diff --cached --check" {
    git diff --cached --check
}

$stagedPaths = @(Get-StagedPaths)
$verifiedFiles = New-Object "System.Collections.Generic.List[object]"
foreach ($stagedPath in $stagedPaths) {
    [void]$verifiedFiles.Add((Resolve-StagedFile $stagedPath))
}

$pythonPaths = @(
    $verifiedFiles |
        Where-Object { [System.IO.Path]::GetExtension($_.RelativePath).ToLowerInvariant() -eq ".py" } |
        ForEach-Object { $_.RelativePath }
)
$webPaths = @(
    $verifiedFiles |
        Where-Object { $webExtensions -contains [System.IO.Path]::GetExtension($_.RelativePath).ToLowerInvariant() } |
        ForEach-Object { $_.RelativePath }
)

if ($pythonPaths.Count -gt 0) {
    Confirm-PythonFormatterDependencies
    Invoke-NativeStep "staged Python formatting" {
        python -m black --check -- @pythonPaths
    }
}

if ($webPaths.Count -gt 0) {
    $binSuffix = if ($isWindows) { ".cmd" } else { "" }
    $prettier = Join-Path $frontendRoot "node_modules/.bin/prettier$binSuffix"
    if (-not (Test-Path -LiteralPath $prettier -PathType Leaf)) {
        Write-Fail (
            "Missing pinned Prettier dependency: $prettier. " +
            "Prepare frontend dependencies with npm install in the frontend directory."
        )
        exit 1
    }

    $frontendRelativePaths = @(
        $webPaths | ForEach-Object {
            if ($_.StartsWith("frontend/", $pathComparison)) {
                $_.Substring("frontend/".Length)
            }
            else {
                "../$_"
            }
        }
    )

    Push-Location $frontendRoot
    try {
        Invoke-NativeStep "staged web and docs formatting" {
            & $prettier --check -- @frontendRelativePaths
        }
    }
    finally {
        Pop-Location
    }
}

Write-Ok "Staged verification complete"
