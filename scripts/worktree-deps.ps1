[CmdletBinding()]
param(
    [ValidateSet("Prepare", "Status", "Detach")]
    [string]$Mode = "Status",
    [AllowEmptyString()]
    [string]$WorktreePath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$runningOnWindows = $env:OS -eq "Windows_NT"
$pathComparer = if ($runningOnWindows) {
    [System.StringComparer]::OrdinalIgnoreCase
}
else {
    [System.StringComparer]::Ordinal
}
$pathComparison = if ($runningOnWindows) {
    [System.StringComparison]::OrdinalIgnoreCase
}
else {
    [System.StringComparison]::Ordinal
}
$trimSeparators = [char[]]@(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)

function Normalize-Path {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "A non-empty filesystem path is required"
    }
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($root, $pathComparison)) {
        return $root
    }
    $trimmed = $fullPath.TrimEnd($trimSeparators)
    return $trimmed
}

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $quoted = New-Object System.Text.StringBuilder
    [void]$quoted.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }
        if ($character -eq '"') {
            [void]$quoted.Append(('\' * (($backslashes * 2) + 1)))
            [void]$quoted.Append('"')
        }
        else {
            [void]$quoted.Append(('\' * $backslashes))
            [void]$quoted.Append($character)
        }
        $backslashes = 0
    }
    [void]$quoted.Append(('\' * ($backslashes * 2)))
    [void]$quoted.Append('"')
    return $quoted.ToString()
}

function Invoke-GitRaw {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $git = Get-Command git -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $git.Source
    $startInfo.Arguments = [string]::Join(
        " ",
        @($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) })
    )
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $stdout = New-Object System.IO.MemoryStream
    try {
        if (-not $process.Start()) {
            throw "Git could not be started"
        }
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardOutput.BaseStream.CopyTo($stdout)
        $process.WaitForExit()
        $stderr = $stderrTask.Result
        if ($process.ExitCode -ne 0) {
            $detail = $stderr.Trim()
            if ($detail.Length -gt 0) {
                throw "Git failed with status $($process.ExitCode): $detail"
            }
            throw "Git failed with status $($process.ExitCode)"
        }
        return [pscustomobject]@{
            Bytes = $stdout.ToArray()
            Stderr = $stderr
        }
    }
    finally {
        $stdout.Dispose()
        $process.Dispose()
    }
}

function ConvertFrom-StrictGitText {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][string]$Description
    )

    try {
        return $strictUtf8.GetString($Bytes)
    }
    catch [System.Text.DecoderFallbackException] {
        throw "Git returned invalid UTF-8 for $Description"
    }
}

function Get-GitSinglePath {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $result = Invoke-GitRaw $Arguments
    $text = ConvertFrom-StrictGitText $result.Bytes $Description
    if ($text.IndexOf([char]0) -ge 0) {
        throw "Git returned invalid path data for $Description"
    }
    $lines = @($text -split "`r?`n" | Where-Object { $_.Length -gt 0 })
    if ($lines.Count -ne 1) {
        throw "Git returned missing or ambiguous path data for $Description"
    }
    return [string]$lines[0]
}

function Get-RegisteredWorktrees {
    param([Parameter(Mandatory = $true)][string]$CommonDirectory)

    try {
        $result = Invoke-GitRaw @(
            "--git-dir", $CommonDirectory, "worktree", "list", "--porcelain", "-z"
        )
    }
    catch {
        throw "Could not read the registered worktree list: $($_.Exception.Message)"
    }
    $bytes = $result.Bytes
    if ($bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -ne 0) {
        throw "Git returned an empty or truncated registered worktree list"
    }
    $text = ConvertFrom-StrictGitText $bytes "the registered worktree list"
    $fields = $text.Split([char]0)
    if ($fields.Count -lt 3 -or
        $fields[$fields.Count - 1].Length -ne 0 -or
        $fields[$fields.Count - 2].Length -ne 0) {
        throw "Git returned malformed registered worktree records"
    }
    $registered = New-Object "System.Collections.Generic.HashSet[string]" ($pathComparer)
    $record = New-Object "System.Collections.Generic.List[string]"
    $primary = $null
    $recordIndex = 0
    for ($index = 0; $index -lt $fields.Count - 1; $index++) {
        $field = $fields[$index]
        if ($field.Length -gt 0) {
            [void]$record.Add($field)
            continue
        }

        if ($record.Count -eq 0 -or
            -not $record[0].StartsWith("worktree ", [System.StringComparison]::Ordinal)) {
            throw "Each registered worktree record must start with one worktree path"
        }
        $worktreeFields = @(
            $record | Where-Object {
                $_.StartsWith("worktree ", [System.StringComparison]::Ordinal)
            }
        )
        if ($worktreeFields.Count -ne 1) {
            throw "Each registered worktree record must contain exactly one worktree path"
        }
        $pathText = $record[0].Substring("worktree ".Length)
        if ([string]::IsNullOrWhiteSpace($pathText) -or
            -not [System.IO.Path]::IsPathRooted($pathText)) {
            throw "Git returned an invalid registered worktree path"
        }
        $registeredPath = Normalize-Path $pathText
        if (-not $registered.Add($registeredPath)) {
            throw "Git returned a duplicate registered worktree path"
        }
        if ($recordIndex -eq 0) {
            $primary = $registeredPath
        }
        $recordIndex++
        $record.Clear()
    }
    if ($record.Count -ne 0 -or $recordIndex -eq 0 -or $null -eq $primary) {
        throw "Git returned no unambiguous primary worktree record"
    }
    return [pscustomobject]@{
        Primary = $primary
        Paths = $registered
    }
}

function Assert-StrictDescendant {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $prefix = $Root + [System.IO.Path]::DirectorySeparatorChar
    if (-not $Candidate.StartsWith($prefix, $pathComparison)) {
        throw "Worktree must be inside the main checkout's .worktrees directory: $Root"
    }
}

function Test-ReparsePoint {
    param([Parameter(Mandatory = $true)]$Item)

    return ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
}

function Test-SafeDirectoryChain {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Leaf,
        [switch]$RequireAll
    )

    $rootPath = Normalize-Path $Root
    $leafPath = Normalize-Path $Leaf
    $paths = New-Object "System.Collections.Generic.List[string]"
    [void]$paths.Add($rootPath)
    if (-not $pathComparer.Equals($rootPath, $leafPath)) {
        $prefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
        if (-not $leafPath.StartsWith($prefix, $pathComparison)) {
            return $false
        }
        $relative = $leafPath.Substring($prefix.Length)
        $current = $rootPath
        foreach ($component in $relative.Split(
            $trimSeparators,
            [System.StringSplitOptions]::RemoveEmptyEntries
        )) {
            $current = Join-Path $current $component
            [void]$paths.Add($current)
        }
    }

    for ($index = 0; $index -lt $paths.Count; $index++) {
        $item = Get-Item -LiteralPath $paths[$index] -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) {
            return $index -gt 0 -and -not $RequireAll
        }
        if (-not $item.PSIsContainer -or (Test-ReparsePoint $item)) {
            return $false
        }
    }
    return $true
}

function Assert-SafeWorktreeBoundary {
    param(
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$AllowedRoot
    )

    $frontend = Join-Path $Target "frontend"
    if (-not (Test-SafeDirectoryChain $AllowedRoot $frontend)) {
        throw "Worktree boundary contains a missing root, non-directory, or reparse point"
    }
    $manifest = Join-Path (Join-Path $Target "frontend") "package.json"
    $manifestItem = Get-Item -LiteralPath $manifest -Force -ErrorAction SilentlyContinue
    if ($null -ne $manifestItem -and (Test-ReparsePoint $manifestItem)) {
        throw "Worktree frontend manifest cannot use a reparse point: $manifest"
    }
}

function Test-SafeMainDependencyChain {
    param(
        [Parameter(Mandatory = $true)][string]$MainRoot,
        [Parameter(Mandatory = $true)][string]$MainModules
    )

    return (Test-SafeDirectoryChain $MainRoot $MainModules -RequireAll)
}

function Get-DependencyStatus {
    param(
        [Parameter(Mandatory = $true)][string]$DependencyPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget,
        [Parameter(Mandatory = $true)][string]$MainRoot
    )

    $state = "missing"
    $stateTarget = $null
    $dependencyItem = Get-Item -LiteralPath $DependencyPath -Force -ErrorAction SilentlyContinue
    if ($null -ne $dependencyItem) {
        if (Test-ReparsePoint $dependencyItem) {
            $state = "unsafe"
            $targets = @($dependencyItem.Target)
            if ($targets.Count -eq 1 -and
                -not [string]::IsNullOrWhiteSpace([string]$targets[0])) {
                try {
                    $targetText = [string]$targets[0]
                    if ([System.IO.Path]::IsPathRooted($targetText)) {
                        $resolvedTarget = Normalize-Path $targetText
                    }
                    else {
                        $parent = [System.IO.Directory]::GetParent($DependencyPath).FullName
                        $resolvedTarget = Normalize-Path (Join-Path $parent $targetText)
                    }
                    $stateTarget = $resolvedTarget
                    if ($runningOnWindows -and
                        [string]$dependencyItem.LinkType -ceq "Junction" -and
                        $pathComparer.Equals($resolvedTarget, $ExpectedTarget) -and
                        (Test-SafeMainDependencyChain $MainRoot $ExpectedTarget)) {
                        $state = "shared"
                    }
                }
                catch {
                    $stateTarget = $null
                }
            }
        }
        elseif ($dependencyItem.PSIsContainer) {
            $state = "isolated"
        }
        else {
            $state = "unsafe"
        }
    }
    return [pscustomobject]@{
        State = $state
        Target = $stateTarget
    }
}

function Assert-RealManifest {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $path = Normalize-Path (Join-Path $Root $RelativePath)
    $parent = [System.IO.Directory]::GetParent($path).FullName
    if (-not (Test-SafeDirectoryChain $Root $parent -RequireAll)) {
        throw "Manifest directory chain is missing, outside its root, or uses a reparse point: $path"
    }
    $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or $item.PSIsContainer -or (Test-ReparsePoint $item)) {
        throw "Manifest must be a real leaf file without reparse points: $path"
    }
    $stage = Invoke-GitRaw @("-C", $Root, "ls-files", "--stage", "--", $RelativePath)
    $stageText = ConvertFrom-StrictGitText $stage.Bytes "manifest index mode"
    $stageLines = @($stageText -split "`r?`n" | Where-Object { $_.Length -gt 0 })
    $expectedSuffix = "`t" + $RelativePath.Replace("\", "/")
    if ($stageLines.Count -ne 1 -or
        $stageLines[0] -notmatch '^100[67][45][45] [0-9a-fA-F]{40,64} 0\s+' -or
        -not $stageLines[0].EndsWith($expectedSuffix, [System.StringComparison]::Ordinal)) {
        throw "Manifest must be a regular Git file, not a Git symlink: $RelativePath"
    }
    return $path
}

function Get-GitManifestObjectId {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $result = Invoke-GitRaw @(
        "-C", $Root, "hash-object", "--path=$RelativePath", "--", $RelativePath
    )
    $text = ConvertFrom-StrictGitText $result.Bytes "the manifest object ID"
    if ($text.IndexOf([char]0) -ge 0) {
        throw "Git returned invalid manifest object ID data: $RelativePath"
    }
    $lines = @($text -split "`r?`n" | Where-Object { $_.Length -gt 0 })
    if ($lines.Count -ne 1 -or $lines[0] -notmatch '^[0-9a-fA-F]{40,64}$') {
        throw "Git returned invalid manifest object ID: $RelativePath"
    }
    return [string]$lines[0]
}

function Assert-CompatibleManifests {
    param(
        [Parameter(Mandatory = $true)][string]$MainRoot,
        [Parameter(Mandatory = $true)][string]$TargetRoot
    )

    foreach ($relativePath in @("frontend/package.json", "frontend/package-lock.json")) {
        $mainPath = Assert-RealManifest $MainRoot $relativePath
        $targetPath = Assert-RealManifest $TargetRoot $relativePath
        $mainObjectId = Get-GitManifestObjectId $MainRoot $relativePath
        $targetObjectId = Get-GitManifestObjectId $TargetRoot $relativePath
        if (-not $mainObjectId.Equals($targetObjectId, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Manifest Git object mismatch requires isolated preparation: $relativePath"
        }
    }
}

function Get-RealTool {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$AllowedExtensions
    )

    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $command) {
        throw "Required tool '$Name' is unavailable; isolated preparation is required"
    }
    $source = Normalize-Path $command.Source
    $item = Get-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
    $extension = [System.IO.Path]::GetExtension($source)
    if ($null -eq $item -or $item.PSIsContainer -or (Test-ReparsePoint $item) -or
        $AllowedExtensions -notcontains $extension.ToLowerInvariant()) {
        throw "Required tool '$Name' must be a direct native entry without reparse points"
    }
    return $source
}

function Invoke-CheckedTool {
    param(
        [Parameter(Mandatory = $true)][string]$Tool,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $argumentText = [string]::Join(
        " ",
        @($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) })
    )
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    if ([System.IO.Path]::GetExtension($Tool).Equals(".cmd", $pathComparison)) {
        $startInfo.FileName = $env:ComSpec
        $commandText = (ConvertTo-NativeArgument $Tool)
        if ($argumentText.Length -gt 0) {
            $commandText += " " + $argumentText
        }
        $startInfo.Arguments = '/d /s /c "' + $commandText + '"'
    }
    else {
        $startInfo.FileName = $Tool
        $startInfo.Arguments = $argumentText
    }
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw "$Description could not be started"
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        if ($process.ExitCode -ne 0) {
            $detail = $stderr.Trim()
            if ($detail.Length -eq 0) {
                $detail = $stdout.Trim()
            }
            if ($detail.Length -gt 0) {
                throw "$Description failed with status $($process.ExitCode): $detail"
            }
            throw "$Description failed with status $($process.ExitCode)"
        }
        return [pscustomobject]@{ Stdout = $stdout; Stderr = $stderr }
    }
    finally {
        $process.Dispose()
    }
}

function Test-ExactJunction {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget
    )

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or -not (Test-ReparsePoint $item) -or
        [string]$item.LinkType -cne "Junction") {
        return $false
    }
    $targets = @($item.Target)
    if ($targets.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$targets[0])) {
        return $false
    }
    try {
        $targetText = [string]$targets[0]
        if (-not [System.IO.Path]::IsPathRooted($targetText)) {
            $targetText = Join-Path ([System.IO.Directory]::GetParent($Path).FullName) $targetText
        }
        return $pathComparer.Equals((Normalize-Path $targetText), $ExpectedTarget)
    }
    catch {
        return $false
    }
}

function Assert-IsolatedInstallInputs {
    param([Parameter(Mandatory = $true)][string]$TargetRoot)

    $frontend = Normalize-Path (Join-Path $TargetRoot "frontend")
    if (-not (Test-SafeDirectoryChain $TargetRoot $frontend -RequireAll)) {
        throw "Target frontend must be a normal real directory for isolated preparation"
    }
    foreach ($relativePath in @("frontend/package.json", "frontend/package-lock.json")) {
        [void](Assert-RealManifest $TargetRoot $relativePath)
    }
    return $frontend
}

function Remove-ExactJunctionLink {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget
    )

    if (-not (Test-ExactJunction $Path $ExpectedTarget)) {
        throw "Dependency path is not the verified junction to the main dependency directory"
    }
    [System.IO.Directory]::Delete($Path, $false)
    if ($null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)) {
        throw "Dependency junction still exists after detach"
    }
}

function Remove-VerifiedSharedJunction {
    param(
        [Parameter(Mandatory = $true)][string]$DependencyPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget,
        [Parameter(Mandatory = $true)][string]$MainRoot,
        [Parameter(Mandatory = $true)][string]$TargetRoot
    )

    $status = Get-DependencyStatus $DependencyPath $ExpectedTarget $MainRoot
    if ($status.State -eq "missing") {
        return
    }
    if ($status.State -ne "shared") {
        throw "Detach only removes a verified junction to the main dependency directory"
    }
    $frontend = Normalize-Path (Join-Path $TargetRoot "frontend")
    if (-not (Test-SafeDirectoryChain $TargetRoot $frontend -RequireAll)) {
        throw "Dependency junction escaped the registered worktree"
    }
    Remove-ExactJunctionLink $DependencyPath $ExpectedTarget
    if (-not (Test-SafeMainDependencyChain $MainRoot $ExpectedTarget)) {
        throw "Main dependency directory became unsafe during detach"
    }
}

function Invoke-IsolatedInstall {
    param(
        [Parameter(Mandatory = $true)][string]$TargetRoot,
        [Parameter(Mandatory = $true)][string]$DependencyPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget,
        [Parameter(Mandatory = $true)][string]$MainRoot
    )

    $frontend = Assert-IsolatedInstallInputs $TargetRoot
    if ($null -ne (Get-Item -LiteralPath $DependencyPath -Force -ErrorAction SilentlyContinue)) {
        throw "Isolated preparation requires a missing dependency path"
    }
    $npm = Get-RealTool "npm" @(".exe", ".cmd")
    [void](Invoke-CheckedTool $npm @("ci") $frontend "npm ci")
    $installed = Get-DependencyStatus $DependencyPath $ExpectedTarget $MainRoot
    if ($installed.State -ne "isolated") {
        throw "Isolated dependency installation did not create a normal directory"
    }
    return $installed
}

try {
    if ([string]::IsNullOrWhiteSpace($WorktreePath)) {
        $currentRootText = Get-GitSinglePath @(
            "-C", [Environment]::CurrentDirectory, "rev-parse", "--show-toplevel"
        ) "the current repository"
        $targetRoot = Normalize-Path $currentRootText
    }
    else {
        $targetRoot = Normalize-Path $WorktreePath
    }

    try {
        $commonText = Get-GitSinglePath @(
            "-C", $targetRoot, "rev-parse", "--git-common-dir"
        ) "the Git common directory"
    }
    catch {
        throw "Target must be a registered worktree: $($_.Exception.Message)"
    }
    if ([System.IO.Path]::IsPathRooted($commonText)) {
        $commonDirectory = Normalize-Path $commonText
    }
    else {
        $commonDirectory = Normalize-Path (Join-Path $targetRoot $commonText)
    }
    $discovery = Get-RegisteredWorktrees $commonDirectory
    $primaryRecord = Normalize-Path ([string]$discovery.Primary)
    $primaryItem = Get-Item -LiteralPath $primaryRecord -Force -ErrorAction SilentlyContinue
    if ($null -eq $primaryItem -or -not $primaryItem.PSIsContainer) {
        throw "Git's primary worktree record must identify an existing directory"
    }
    if ($pathComparer.Equals($primaryRecord, $commonDirectory)) {
        $configuredMainText = Get-GitSinglePath @(
            "--git-dir", $commonDirectory, "config", "--path", "--get", "core.worktree"
        ) "the separate Git directory's primary worktree"
        if ([System.IO.Path]::IsPathRooted($configuredMainText)) {
            $mainRoot = Normalize-Path $configuredMainText
        }
        else {
            $mainRoot = Normalize-Path (Join-Path $commonDirectory $configuredMainText)
        }
    }
    else {
        $mainRoot = $primaryRecord
    }
    $mainItem = Get-Item -LiteralPath $mainRoot -Force -ErrorAction SilentlyContinue
    if ($null -eq $mainItem -or
        -not $mainItem.PSIsContainer -or
        (Test-ReparsePoint $mainItem)) {
        throw "Git's primary worktree must exist as a normal directory"
    }
    $primaryCommonText = Get-GitSinglePath @(
        "-C", $mainRoot, "rev-parse", "--git-common-dir"
    ) "the primary worktree Git common directory"
    if ([System.IO.Path]::IsPathRooted($primaryCommonText)) {
        $primaryCommonDirectory = Normalize-Path $primaryCommonText
    }
    else {
        $primaryCommonDirectory = Normalize-Path (Join-Path $mainRoot $primaryCommonText)
    }
    if (-not $pathComparer.Equals($primaryCommonDirectory, $commonDirectory)) {
        throw "Git's primary and target worktrees do not share one common directory"
    }
    if ($pathComparer.Equals($targetRoot, $mainRoot)) {
        throw "Dependency reuse status requires a temporary worktree, not the main checkout"
    }

    $allowedRoot = Normalize-Path (Join-Path $mainRoot ".worktrees")
    Assert-StrictDescendant $targetRoot $allowedRoot
    if (-not $discovery.Paths.Contains($targetRoot)) {
        throw "Target must be present in Git's registered worktree list"
    }
    Assert-SafeWorktreeBoundary $targetRoot $allowedRoot

    $dependencyPath = Normalize-Path (
        Join-Path (Join-Path $targetRoot "frontend") "node_modules"
    )
    $expectedTarget = Normalize-Path (
        Join-Path (Join-Path $mainRoot "frontend") "node_modules"
    )
    $dependencyStatus = Get-DependencyStatus $dependencyPath $expectedTarget $mainRoot
    if ($Mode -eq "Detach") {
        Remove-VerifiedSharedJunction `
            $dependencyPath $expectedTarget $mainRoot $targetRoot
        $dependencyStatus = Get-DependencyStatus $dependencyPath $expectedTarget $mainRoot
    }
    elseif ($Mode -eq "Prepare") {
        if ($dependencyStatus.State -eq "isolated") {
            # An existing normal directory is already a safe isolated preparation.
        }
        elseif ($dependencyStatus.State -eq "unsafe") {
            throw "Unsafe dependency path cannot be prepared or overwritten; isolated preparation is required"
        }
        elseif ($dependencyStatus.State -eq "shared") {
            [void](Assert-IsolatedInstallInputs $targetRoot)
            $sharedCompatible = $true
            try {
                Assert-CompatibleManifests $mainRoot $targetRoot
                if (-not (Test-SafeMainDependencyChain $mainRoot $expectedTarget)) {
                    throw "Shared main dependency chain is unsafe"
                }
            }
            catch {
                $sharedCompatible = $false
            }
            if (-not $sharedCompatible) {
                Remove-VerifiedSharedJunction `
                    $dependencyPath $expectedTarget $mainRoot $targetRoot
                $dependencyStatus = Invoke-IsolatedInstall `
                    $targetRoot $dependencyPath $expectedTarget $mainRoot
            }
        }
        else {
            [void](Assert-IsolatedInstallInputs $targetRoot)
            $reuseReady = $true
            try {
                Assert-CompatibleManifests $mainRoot $targetRoot
                if (-not (Test-SafeMainDependencyChain $mainRoot $expectedTarget)) {
                    throw "Main node_modules must be a normal real directory"
                }
                $node = Get-RealTool "node" @(".exe")
                $npm = Get-RealTool "npm" @(".exe", ".cmd")
                [void](Invoke-CheckedTool $node @("--version") $targetRoot "node --version")
                $mainFrontend = Normalize-Path (Join-Path $mainRoot "frontend")
                [void](Invoke-CheckedTool $npm @("ls", "--depth=0", "--json") $mainFrontend "npm ls")
            }
            catch {
                $reuseReady = $false
            }
            if (-not $reuseReady) {
                $dependencyStatus = Invoke-IsolatedInstall `
                    $targetRoot $dependencyPath $expectedTarget $mainRoot
            }
            else {
                if ($null -ne (Get-Item -LiteralPath $dependencyPath -Force -ErrorAction SilentlyContinue)) {
                    throw "Dependency path appeared concurrently; refusing to overwrite it"
                }
                $created = $false
                try {
                    [void](New-Item -ItemType Junction -Path $dependencyPath -Target $expectedTarget -ErrorAction Stop)
                    $created = $true
                    $dependencyStatus = Get-DependencyStatus $dependencyPath $expectedTarget $mainRoot
                    if ($dependencyStatus.State -ne "shared") {
                        throw "Created dependency junction did not verify as shared"
                    }
                }
                catch {
                    $creationError = $_.Exception.Message
                    if ($created -and (Test-ExactJunction $dependencyPath $expectedTarget)) {
                        Remove-ExactJunctionLink $dependencyPath $expectedTarget
                    }
                    throw "Could not create a verified shared dependency junction: $creationError"
                }
            }
        }
    }

    [pscustomobject]@{
        state = $dependencyStatus.State
        worktree = $targetRoot
        dependencyPath = $dependencyPath
        target = $dependencyStatus.Target
    } | ConvertTo-Json -Compress
}
catch {
    $message = $_.Exception.Message
    if ($Mode -eq "Prepare" -and
        $message.IndexOf("isolated", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        $message += "; isolated preparation failed safely"
    }
    [System.Console]::Error.WriteLine("worktree-deps: $message")
    exit 1
}
