[CmdletBinding()]
param(
    [ValidateSet("Prepare", "Status", "Detach")]
    [string]$Mode = "Status",
    [AllowEmptyString()]
    [string]$WorktreePath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$isWindows = $env:OS -eq "Windows_NT"
$pathComparer = if ($isWindows) {
    [System.StringComparer]::OrdinalIgnoreCase
}
else {
    [System.StringComparer]::Ordinal
}
$pathComparison = if ($isWindows) {
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

if ($Mode -ne "Status") {
    throw "Mode '$Mode' is not implemented"
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
    $state = "missing"
    $stateTarget = $null
    $dependencyItem = Get-Item -LiteralPath $dependencyPath -Force -ErrorAction SilentlyContinue
    if ($null -ne $dependencyItem) {
        if (Test-ReparsePoint $dependencyItem) {
            $state = "unsafe"
            $targets = @($dependencyItem.Target)
            if ($targets.Count -eq 1 -and
                -not [string]::IsNullOrWhiteSpace([string]$targets[0])) {
                try {
                    $targetText = [string]$targets[0]
                    if ([System.IO.Path]::IsPathRooted($targetText)) {
                        $resolvedTarget = Normalize-Path ([string]$targets[0])
                    }
                    else {
                        $resolvedTarget = Normalize-Path (
                            Join-Path ([System.IO.Directory]::GetParent($dependencyPath).FullName) $targetText
                        )
                    }
                    $stateTarget = $resolvedTarget
                    if ($isWindows -and
                        [string]$dependencyItem.LinkType -ceq "Junction" -and
                        $pathComparer.Equals($resolvedTarget, $expectedTarget) -and
                        (Test-SafeMainDependencyChain $mainRoot $expectedTarget)) {
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

    [pscustomobject]@{
        state = $state
        worktree = $targetRoot
        dependencyPath = $dependencyPath
        target = $stateTarget
    } | ConvertTo-Json -Compress
}
catch {
    [System.Console]::Error.WriteLine("worktree-deps: $($_.Exception.Message)")
    exit 1
}
