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
    param(
        [string]$Path,
        [string]$AllowedReparsePath = ""
    )

    $current = $projectRoot
    $item = Get-Item -LiteralPath $current -Force
    if (
        ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and
        -not $current.Equals($AllowedReparsePath, $pathComparison)
    ) {
        return $true
    }

    $relativePath = $Path.Substring($projectRootPrefix.Length)
    foreach ($segment in $relativePath.Split(
        [char[]]@('\', '/'),
        [System.StringSplitOptions]::RemoveEmptyEntries
    )) {
        $current = Join-Path $current $segment
        $item = Get-Item -LiteralPath $current -Force
        if (
            ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and
            -not $current.Equals($AllowedReparsePath, $pathComparison)
        ) {
            return $true
        }
    }
    return $false
}

function Test-PathFromRootHasReparsePoint {
    param(
        [string]$Path,
        [string]$Root,
        [string]$RootPrefix
    )

    $current = $Root
    $item = Get-Item -LiteralPath $current -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        return $true
    }
    $relativePath = $Path.Substring($RootPrefix.Length)
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

function Get-PythonFormatterCommand {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        Write-Fail (
            "Missing Python executable. Install Python 3, ensure python is on PATH, " +
            "then run: python -m pip install black"
        )
        exit 1
    }
    return $pythonCommand
}

function Get-NodeCommand {
    $nodeCommand = Get-Command node -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $nodeCommand) {
        Write-Fail (
            "Missing Node.js executable. Install Node.js and ensure node is on PATH, " +
            "then run npm install in the frontend directory."
        )
        exit 1
    }
    if (
        $isWindows -and
        [System.IO.Path]::GetExtension($nodeCommand.Source).ToLowerInvariant() -ne ".exe"
    ) {
        Write-Fail "Node.js must resolve to a native node.exe executable on Windows."
        exit 1
    }
    return $nodeCommand
}

function Get-RegisteredWorktreeRoots {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.Arguments = "worktree list --porcelain -z"
    $startInfo.WorkingDirectory = $projectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            Write-Fail "Could not start Git to enumerate registered worktrees"
            exit 1
        }
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $fields = New-Object "System.Collections.Generic.List[string]"
        $fieldBytes = New-Object "System.Collections.Generic.List[byte]"
        $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
        [byte[]]$buffer = New-Object byte[] 4096
        $stdout = $process.StandardOutput.BaseStream
        $decodeFailed = $false

        while (($bytesRead = $stdout.Read($buffer, 0, $buffer.Length)) -gt 0) {
            for ($index = 0; $index -lt $bytesRead; $index++) {
                if ($buffer[$index] -eq 0) {
                    if ($fieldBytes.Count -gt 0) {
                        try {
                            [void]$fields.Add($strictUtf8.GetString($fieldBytes.ToArray()))
                        }
                        catch [System.Text.DecoderFallbackException] {
                            $decodeFailed = $true
                        }
                    }
                    $fieldBytes.Clear()
                }
                else {
                    [void]$fieldBytes.Add($buffer[$index])
                }
            }
        }

        $process.WaitForExit()
        $stderr = $stderrTask.Result
        $exitCode = $process.ExitCode
        if ($exitCode -ne 0) {
            $detail = $stderr.Trim()
            if ($detail.Length -gt 0) {
                Write-Fail "Could not enumerate registered worktrees: $detail"
            }
            else {
                Write-Fail "Could not enumerate registered worktrees"
            }
            exit $exitCode
        }
        if ($decodeFailed -or $fieldBytes.Count -ne 0) {
            Write-Fail "Git returned invalid UTF-8 or truncated registered worktree data"
            exit 1
        }

        $roots = New-Object "System.Collections.Generic.List[string]"
        foreach ($field in $fields) {
            if ($field.StartsWith("worktree ", [System.StringComparison]::Ordinal)) {
                $rootText = $field.Substring("worktree ".Length)
                if (-not [System.IO.Path]::IsPathRooted($rootText)) {
                    Write-Fail "Git returned a non-absolute registered worktree path"
                    exit 1
                }
                try {
                    [void]$roots.Add([System.IO.Path]::GetFullPath($rootText))
                }
                catch {
                    Write-Fail "Git returned an invalid registered worktree path"
                    exit 1
                }
            }
        }
        return $roots.ToArray()
    }
    catch {
        Write-Fail "Could not enumerate registered worktrees: $($_.Exception.Message)"
        exit 1
    }
    finally {
        $process.Dispose()
    }
}

function Get-FileSha256 {
    param([string]$Path)

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash($stream)
        return [System.BitConverter]::ToString($hash).Replace("-", "")
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

function Confirm-ApprovedNodeModulesJunction {
    param([string]$NodeModulesRoot)

    if (-not $isWindows) {
        Write-Fail "frontend/node_modules reparse points are allowed only for Windows junction reuse"
        exit 1
    }
    $nodeModulesItem = Get-Item -LiteralPath $NodeModulesRoot -Force
    if ([string]$nodeModulesItem.LinkType -cne "Junction") {
        Write-Fail "frontend/node_modules reparse reuse must be a Windows junction"
        exit 1
    }
    $junctionTargets = @($nodeModulesItem.Target)
    if ($junctionTargets.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$junctionTargets[0])) {
        Write-Fail "frontend/node_modules junction must expose exactly one target"
        exit 1
    }
    try {
        $targetNodeModules = [System.IO.Path]::GetFullPath([string]$junctionTargets[0]).TrimEnd([char[]]@('\', '/'))
    }
    catch {
        Write-Fail "frontend/node_modules junction target is invalid"
        exit 1
    }

    $targetWorktree = $null
    foreach ($registeredRoot in @(Get-RegisteredWorktreeRoots)) {
        $normalizedRoot = $registeredRoot.TrimEnd([char[]]@('\', '/'))
        if ($normalizedRoot.Equals($projectRoot, $pathComparison)) {
            continue
        }
        try {
            $registeredNodeModules = [System.IO.Path]::GetFullPath(
                (Join-Path (Join-Path $normalizedRoot "frontend") "node_modules")
            ).TrimEnd([char[]]@('\', '/'))
        }
        catch {
            Write-Fail "Registered worktree path could not be normalized safely"
            exit 1
        }
        if ($registeredNodeModules.Equals($targetNodeModules, $pathComparison)) {
            $targetWorktree = $normalizedRoot
            break
        }
    }
    if ($null -eq $targetWorktree) {
        Write-Fail (
            "frontend/node_modules junction target must exactly match a registered " +
            "other worktree's frontend/node_modules"
        )
        exit 1
    }
    if (-not (Test-Path -LiteralPath $targetWorktree -PathType Container)) {
        Write-Fail "Registered target worktree is missing"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $targetNodeModules -PathType Container)) {
        Write-Fail "Registered target worktree node_modules is missing"
        exit 1
    }
    $targetWorktreePrefix = $targetWorktree + [System.IO.Path]::DirectorySeparatorChar
    if (Test-PathFromRootHasReparsePoint $targetNodeModules $targetWorktree $targetWorktreePrefix) {
        Write-Fail "Registered target worktree node_modules cannot contain a reparse ancestor"
        exit 1
    }

    foreach ($manifestName in @("package.json", "package-lock.json")) {
        $currentManifest = Join-Path $frontendRoot $manifestName
        $targetManifest = Join-Path (Join-Path $targetWorktree "frontend") $manifestName
        if (
            -not (Test-Path -LiteralPath $currentManifest -PathType Leaf) -or
            -not (Test-Path -LiteralPath $targetManifest -PathType Leaf)
        ) {
            Write-Fail "Both worktrees must contain frontend/$manifestName for junction approval"
            exit 1
        }
        if (
            (Test-PathHasReparsePoint $currentManifest) -or
            (Test-PathFromRootHasReparsePoint $targetManifest $targetWorktree $targetWorktreePrefix)
        ) {
            Write-Fail "Frontend junction approval manifests cannot use reparse paths"
            exit 1
        }
        if ((Get-FileSha256 $currentManifest) -cne (Get-FileSha256 $targetManifest)) {
            Write-Fail "Frontend junction approval manifest contents must match: $manifestName"
            exit 1
        }
    }
    return $targetNodeModules
}

function Resolve-PinnedPrettierCli {
    $nodeModulesRoot = Join-Path $frontendRoot "node_modules"
    $allowedReparsePath = ""
    $approvedTargetNodeModules = $null
    if (Test-Path -LiteralPath $nodeModulesRoot -PathType Container) {
        $nodeModulesItem = Get-Item -LiteralPath $nodeModulesRoot -Force
        if (($nodeModulesItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            $approvedTargetNodeModules = Confirm-ApprovedNodeModulesJunction $nodeModulesRoot
            $allowedReparsePath = $nodeModulesRoot
        }
    }

    $packageRoot = Join-Path $nodeModulesRoot "prettier"
    $packageRootPrefix = $packageRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    $approvedTargetPackagePrefix = ""
    if ($null -ne $approvedTargetNodeModules) {
        $approvedTargetPackagePrefix = (Join-Path $approvedTargetNodeModules "prettier").TrimEnd(
            [char[]]@('\', '/')
        ) + [System.IO.Path]::DirectorySeparatorChar
    }
    if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
        Write-Fail (
            "Missing pinned Prettier package: $packageRoot. " +
            "Prepare frontend dependencies with npm install in the frontend directory."
        )
        exit 1
    }
    if (Test-PathHasReparsePoint $packageRoot $allowedReparsePath) {
        Write-Fail "Pinned Prettier package cannot be a symbolic link or reparse point: $packageRoot"
        exit 1
    }

    $packageJsonPath = Join-Path $packageRoot "package.json"
    if (-not (Test-Path -LiteralPath $packageJsonPath -PathType Leaf)) {
        Write-Fail "Missing pinned Prettier package metadata: $packageJsonPath"
        exit 1
    }
    if (Test-PathHasReparsePoint $packageJsonPath $allowedReparsePath) {
        Write-Fail "Pinned Prettier package metadata cannot be a symbolic link or reparse point"
        exit 1
    }

    try {
        $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
        $packageJson = [System.IO.File]::ReadAllText($packageJsonPath, $strictUtf8)
        $packageMetadata = $packageJson | ConvertFrom-Json
    }
    catch {
        Write-Fail "Could not read pinned Prettier package metadata as strict UTF-8 JSON"
        exit 1
    }
    if ([string]$packageMetadata.version -cne "3.6.2") {
        Write-Fail (
            "Pinned Prettier package version must be exactly 3.6.2; found: " +
            [string]$packageMetadata.version
        )
        exit 1
    }

    $binEntry = $null
    if ($packageMetadata.bin -is [string]) {
        $binEntry = [string]$packageMetadata.bin
    }
    elseif ($null -ne $packageMetadata.bin -and $null -ne $packageMetadata.bin.prettier) {
        $binEntry = [string]$packageMetadata.bin.prettier
    }
    if ([string]::IsNullOrWhiteSpace($binEntry)) {
        Write-Fail "Pinned Prettier package metadata has no CLI entry"
        exit 1
    }
    if ([System.IO.Path]::IsPathRooted($binEntry)) {
        Write-Fail "Pinned Prettier CLI entry must stay within its package"
        exit 1
    }
    if (@($binEntry -split "[\\/]" | Where-Object { $_ -eq ".." }).Count -gt 0) {
        Write-Fail "Pinned Prettier CLI entry must stay within its package"
        exit 1
    }

    try {
        $entryHostPath = $binEntry.Replace(
            "/",
            [System.IO.Path]::DirectorySeparatorChar
        )
        $entryCandidate = [System.IO.Path]::GetFullPath((Join-Path $packageRoot $entryHostPath))
    }
    catch {
        Write-Fail "Pinned Prettier CLI entry is invalid"
        exit 1
    }
    if (-not $entryCandidate.StartsWith($packageRootPrefix, $pathComparison)) {
        Write-Fail "Pinned Prettier CLI entry must stay within its package"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $entryCandidate -PathType Leaf)) {
        Write-Fail "Pinned Prettier CLI entry is missing or is not a real file: $entryCandidate"
        exit 1
    }
    if (Test-PathHasReparsePoint $entryCandidate $allowedReparsePath) {
        Write-Fail "Pinned Prettier CLI entry cannot be a symbolic link or reparse point"
        exit 1
    }
    $entryExtension = [System.IO.Path]::GetExtension($entryCandidate).ToLowerInvariant()
    if (@(".cjs", ".js", ".mjs") -notcontains $entryExtension) {
        Write-Fail "Pinned Prettier CLI entry must be a JavaScript file"
        exit 1
    }

    try {
        $resolvedEntry = (Resolve-Path -LiteralPath $entryCandidate).Path
    }
    catch {
        Write-Fail "Could not resolve pinned Prettier CLI entry"
        exit 1
    }
    if (
        -not $resolvedEntry.StartsWith($packageRootPrefix, $pathComparison) -and
        (
            $approvedTargetPackagePrefix.Length -eq 0 -or
            -not $resolvedEntry.StartsWith($approvedTargetPackagePrefix, $pathComparison)
        )
    ) {
        Write-Fail "Resolved Prettier CLI entry must stay within its package"
        exit 1
    }
    return $resolvedEntry
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
    $pythonCommand = Get-PythonFormatterCommand
    Write-Info "staged Python formatting"
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $blackOutput = @()
    try {
        $blackOutput = @(& $pythonCommand.Source -m black --check -- @pythonPaths 2>&1)
        $blackExitCode = $LASTEXITCODE
    }
    catch {
        Write-Fail (
            "Could not start Python formatter. Prepare Python and Black with: " +
            "python -m pip install black"
        )
        exit 1
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    $blackStderrParts = New-Object "System.Collections.Generic.List[string]"
    foreach ($outputItem in $blackOutput) {
        if ($outputItem -is [System.Management.Automation.ErrorRecord]) {
            $message = $outputItem.Exception.Message
            [void]$blackStderrParts.Add($message)
            [System.Console]::Error.WriteLine($message)
        }
        else {
            [System.Console]::Out.WriteLine([string]$outputItem)
        }
    }
    $blackStderr = [string]::Join([System.Environment]::NewLine, $blackStderrParts.ToArray())
    if ($blackExitCode -ne 0) {
        $missingBlack = $blackStderr -match "(?is)(No module named.*black|ModuleNotFoundError.*black|ImportError.*black)"
        if ($missingBlack) {
            Write-Fail (
                "Python formatter dependency Black is missing or cannot be imported. " +
                "Prepare it with: python -m pip install black"
            )
        }
        else {
            Write-Fail (
                "staged Python formatting failed. Fix the reported formatting error, " +
                "stage the corrected file, and retry."
            )
        }
        exit $blackExitCode
    }
    Write-Ok "staged Python formatting"
}

if ($webPaths.Count -gt 0) {
    $nodeCommand = Get-NodeCommand
    $prettierCli = Resolve-PinnedPrettierCli

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
            & $nodeCommand.Source $prettierCli --check -- @frontendRelativePaths
        }
    }
    finally {
        Pop-Location
    }
}

Write-Ok "Staged verification complete"
