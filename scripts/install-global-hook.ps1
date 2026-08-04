#requires -Version 5.1
param(
    [string]$HookDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Write-Failure {
    param([string]$Message)

    [System.Console]::Error.WriteLine("[hook-installer] $Message")
}

function Get-NormalizedAbsolutePath {
    param(
        [string]$Path,
        [string]$Description
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "$Description is missing."
    }
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        throw "$Description must be an absolute path."
    }
    $segments = @($Path -split "[\\/]" | Where-Object { $_.Length -gt 0 })
    if (@($segments | Where-Object { $_ -eq "." -or $_ -eq ".." }).Count -gt 0) {
        throw "$Description is unsafe because it contains dot path segments."
    }
    try {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd(
            [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
        )
    }
    catch {
        throw "$Description is not a valid absolute path: $($_.Exception.Message)"
    }
}

function Assert-ExistingPathWithoutReparse {
    param(
        [string]$Path,
        [string]$Description
    )

    $fullPath = Get-NormalizedAbsolutePath $Path $Description
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::IsNullOrEmpty($pathRoot)) {
        throw "$Description has no filesystem root."
    }
    $current = $pathRoot.TrimEnd([char[]]@('\', '/'))
    if ($current.Length -eq 2 -and $current[1] -eq ':') {
        $current += [System.IO.Path]::DirectorySeparatorChar
    }
    $relative = $fullPath.Substring($pathRoot.Length)
    foreach ($segment in @($relative -split "[\\/]" | Where-Object { $_.Length -gt 0 })) {
        $current = Join-Path $current $segment
        if (-not [System.IO.File]::Exists($current) -and -not [System.IO.Directory]::Exists($current)) {
            throw "$Description contains a missing path component: $current"
        }
        $item = Get-Item -LiteralPath $current -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Description cannot contain a symbolic link or reparse point: $current"
        }
    }
    return $fullPath
}

function Assert-DirectChild {
    param(
        [string]$Directory,
        [string]$Child,
        [string]$Description
    )

    $parent = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($Child))
    if (-not $parent.Equals($Directory, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Description must be a direct child of the hook directory."
    }
}

function Assert-RegularDestination {
    param([string]$Destination)

    if ([System.IO.Directory]::Exists($Destination)) {
        throw "Hook destination cannot be a directory: $Destination"
    }
    if ([System.IO.File]::Exists($Destination)) {
        $item = Get-Item -LiteralPath $Destination -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Hook destination cannot be a symbolic link or reparse point: $Destination"
        }
    }
    elseif (Test-Path -LiteralPath $Destination) {
        throw "Hook destination is not a regular file path: $Destination"
    }
}

function Set-RestrictedFileAcl {
    param([string]$Path)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $security = New-Object System.Security.AccessControl.FileSecurity
    $security.SetOwner($identity)
    $security.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    [void]$security.AddAccessRule($rule)
    [System.IO.File]::SetAccessControl($Path, $security)
}

function New-OwnedCopy {
    param(
        [string]$Source,
        [string]$Destination
    )

    $sourceStream = $null
    $destinationStream = $null
    $createdDestination = $false
    $completedCopy = $false
    try {
        $destinationStream = New-Object System.IO.FileStream(
            $Destination,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None,
            65536,
            [System.IO.FileOptions]::WriteThrough
        )
        $createdDestination = $true
        Set-RestrictedFileAcl $Destination
        $sourceStream = New-Object System.IO.FileStream(
            $Source,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read,
            65536,
            [System.IO.FileOptions]::SequentialScan
        )
        $sourceStream.CopyTo($destinationStream)
        $destinationStream.Flush($true)
        $completedCopy = $true
    }
    finally {
        if ($null -ne $sourceStream) {
            $sourceStream.Dispose()
        }
        if ($null -ne $destinationStream) {
            $destinationStream.Dispose()
        }
        if (
            $createdDestination -and
            -not $completedCopy -and
            [System.IO.File]::Exists($Destination)
        ) {
            [System.IO.File]::Delete($Destination)
        }
    }
}

function Get-FileHashHex {
    param([string]$Path)

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.BitConverter]::ToString($sha256.ComputeHash($stream)).Replace("-", "")
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

function New-UniqueChildPath {
    param(
        [string]$Directory,
        [string]$Prefix,
        [string]$Suffix
    )

    for ($attempt = 0; $attempt -lt 16; $attempt++) {
        $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss-fff")
        $token = [Guid]::NewGuid().ToString("N")
        $candidate = Join-Path $Directory "$Prefix$stamp-$token$Suffix"
        Assert-DirectChild $Directory $candidate "Generated path"
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    throw "Could not allocate a collision-free path in the hook directory."
}

function Restore-InstalledHook {
    param(
        [string]$Directory,
        [string]$Destination,
        [string]$Backup,
        [bool]$HadDestination,
        [string]$InstalledHash
    )

    Assert-RegularDestination $Destination
    if (-not [System.IO.File]::Exists($Destination)) {
        throw "Cannot roll back because the installed hook disappeared: $Destination"
    }
    if ((Get-FileHashHex $Destination) -cne $InstalledHash) {
        throw "Cannot roll back because the installed hook changed concurrently: $Destination"
    }
    if ($HadDestination) {
        if (-not [System.IO.File]::Exists($Backup)) {
            throw "Cannot roll back because the backup is missing: $Backup"
        }
        $rollbackTemporary = New-UniqueChildPath $Directory "pre-commit.installing-rollback-" ".tmp"
        $rollbackDisplaced = New-UniqueChildPath $Directory "pre-commit.installing-displaced-" ".tmp"
        $ownsRollbackTemporary = $false
        $ownsRollbackDisplaced = $false
        try {
            New-OwnedCopy $Backup $rollbackTemporary
            $ownsRollbackTemporary = $true
            [System.IO.File]::Replace(
                $rollbackTemporary,
                $Destination,
                $rollbackDisplaced,
                $true
            )
            $ownsRollbackTemporary = $false
            $ownsRollbackDisplaced = $true
        }
        finally {
            if ($ownsRollbackTemporary -and [System.IO.File]::Exists($rollbackTemporary)) {
                [System.IO.File]::Delete($rollbackTemporary)
            }
            if ($ownsRollbackDisplaced -and [System.IO.File]::Exists($rollbackDisplaced)) {
                [System.IO.File]::Delete($rollbackDisplaced)
            }
        }
    }
    else {
        [System.IO.File]::Delete($Destination)
    }
}

try {
    $rootOutput = @(& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or $rootOutput.Count -ne 1) {
        throw "Could not resolve exactly one repository root with Git."
    }
    $repositoryRoot = Assert-ExistingPathWithoutReparse $rootOutput[0] "Repository root"
    if (-not [System.IO.Directory]::Exists($repositoryRoot)) {
        throw "Git repository root is not a directory: $repositoryRoot"
    }

    $expectedScript = Join-Path (Join-Path $repositoryRoot "scripts") "install-global-hook.ps1"
    $actualScript = [System.IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
    if (-not $actualScript.Equals($expectedScript, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Installer must run from the repository's fixed scripts/install-global-hook.ps1 path."
    }
    [void](Assert-ExistingPathWithoutReparse $actualScript "Installer source path")

    $sourceRelative = "scripts/git-hooks/pre-commit"
    $source = Join-Path $repositoryRoot ($sourceRelative.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    [void](Assert-ExistingPathWithoutReparse $source "Hook template source")
    if (-not [System.IO.File]::Exists($source) -or [System.IO.Directory]::Exists($source)) {
        throw "Hook template source must be an existing regular file: $source"
    }
    $sourceIndex = @(& git -C $repositoryRoot ls-files --stage -- $sourceRelative 2>$null)
    if ($LASTEXITCODE -ne 0 -or $sourceIndex.Count -ne 1) {
        throw "Hook template source must be exactly one Git-tracked regular file."
    }
    $sourceMode = @($sourceIndex[0] -split "\s+")[0]
    if ($sourceMode -eq "120000") {
        throw "Hook template source cannot use Git symbolic link mode 120000."
    }
    if (@("100644", "100755") -notcontains $sourceMode) {
        throw "Hook template source has an unsupported Git mode: $sourceMode"
    }

    if ([string]::IsNullOrWhiteSpace($HookDirectory)) {
        $globalHookValues = @(& git config --global --get-all core.hooksPath 2>$null)
        $globalConfigExit = $LASTEXITCODE
        if ($globalConfigExit -gt 1) {
            throw "Could not read global core.hooksPath."
        }
        if ($globalHookValues.Count -ne 1 -or [string]::IsNullOrWhiteSpace($globalHookValues[0])) {
            throw "Global core.hooksPath must contain exactly one non-empty value."
        }
        $HookDirectory = $globalHookValues[0]
    }

    $directory = Get-NormalizedAbsolutePath $HookDirectory "Hook directory"
    if ([System.IO.File]::Exists($directory)) {
        throw "Hook directory path is an existing file: $directory"
    }
    if (-not [System.IO.Directory]::Exists($directory)) {
        $parent = [System.IO.Path]::GetDirectoryName($directory)
        if ([string]::IsNullOrEmpty($parent) -or -not [System.IO.Directory]::Exists($parent)) {
            throw "Hook directory parent must already exist: $parent"
        }
        [void](Assert-ExistingPathWithoutReparse $parent "Hook directory parent")
        [void][System.IO.Directory]::CreateDirectory($directory)
    }
    [void](Assert-ExistingPathWithoutReparse $directory "Hook directory")

    $destination = Join-Path $directory "pre-commit"
    Assert-DirectChild $directory $destination "Hook destination"
    Assert-RegularDestination $destination
    $hadDestination = [System.IO.File]::Exists($destination)
    $backup = $null
    if ($hadDestination) {
        $backup = New-UniqueChildPath $directory "pre-commit.backup-" ".bak"
        Assert-DirectChild $directory $backup "Hook backup"
    }
    $temporary = New-UniqueChildPath $directory "pre-commit.installing-" ".tmp"
    Assert-DirectChild $directory $temporary "Hook temporary file"

    $ownsTemporary = $false
    $installed = $false
    try {
        New-OwnedCopy $source $temporary
        $ownsTemporary = $true
        Assert-RegularDestination $destination
        if ($hadDestination) {
            [System.IO.File]::Replace($temporary, $destination, $backup, $true)
        }
        else {
            [System.IO.File]::Move($temporary, $destination)
        }
        $ownsTemporary = $false
        $installed = $true
        $installedHash = Get-FileHashHex $source

        $configOutput = @(& git config --local workflow.useRepositoryHook true 2>&1)
        $configExit = $LASTEXITCODE
        if ($configExit -ne 0) {
            $detail = [string]::Join([System.Environment]::NewLine, @($configOutput | ForEach-Object { [string]$_ }))
            throw "Failed to set repository opt-in with local Git config. $detail"
        }
        $configuredValues = @(& git config --local --get-all workflow.useRepositoryHook 2>$null)
        if ($LASTEXITCODE -ne 0 -or $configuredValues.Count -ne 1 -or $configuredValues[0] -cne "true") {
            throw "Local workflow.useRepositoryHook must be exactly one value equal to true."
        }
    }
    catch {
        $primaryFailure = $_.Exception.Message
        if ($installed) {
            try {
                Restore-InstalledHook $directory $destination $backup $hadDestination $installedHash
            }
            catch {
                throw "$primaryFailure Rollback also failed: $($_.Exception.Message)"
            }
        }
        throw $primaryFailure
    }
    finally {
        if ($ownsTemporary -and [System.IO.File]::Exists($temporary)) {
            [System.IO.File]::Delete($temporary)
        }
    }

    Write-Host "Installed: $destination"
    if ($hadDestination) {
        Write-Host "Backup: $backup"
        $quotedBackup = $backup.Replace("'", "''")
        $quotedDestination = $destination.Replace("'", "''")
        Write-Host "Restore: Copy-Item -LiteralPath '$quotedBackup' -Destination '$quotedDestination' -Force"
    }
    else {
        $quotedDestination = $destination.Replace("'", "''")
        Write-Host "Restore: Remove-Item -LiteralPath '$quotedDestination'"
    }
}
catch {
    Write-Failure $_.Exception.Message
    exit 1
}
