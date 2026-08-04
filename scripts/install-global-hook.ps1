#requires -Version 5.1
param(
    [string]$HookDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0
$script:InstallerScriptPath = [System.IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)

if (-not ("HookInstaller.NativeFileIdentity" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace HookInstaller {
    public static class NativeFileIdentity {
        [StructLayout(LayoutKind.Sequential)]
        private struct FileInformation {
            public uint FileAttributes;
            public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
            public uint VolumeSerialNumber;
            public uint FileSizeHigh;
            public uint FileSizeLow;
            public uint NumberOfLinks;
            public uint FileIndexHigh;
            public uint FileIndexLow;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetFileInformationByHandle(
            SafeFileHandle handle,
            out FileInformation information
        );

        public static string FromHandle(SafeFileHandle handle) {
            FileInformation information;
            if (!GetFileInformationByHandle(handle, out information)) {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            return String.Format(
                "{0:X8}:{1:X8}{2:X8}",
                information.VolumeSerialNumber,
                information.FileIndexHigh,
                information.FileIndexLow
            );
        }

        public static string FromPath(string path) {
            using (FileStream stream = new FileStream(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete
            )) {
                return FromHandle(stream.SafeFileHandle);
            }
        }
    }
}
"@
}

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
        $fullPath = [System.IO.Path]::GetFullPath($Path)
        $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
        if ($fullPath.Equals($pathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $pathRoot
        }
        return $fullPath.TrimEnd(
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

function Assert-RestrictedFileAcl {
    param([string]$Path)

    $currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $security = [System.IO.File]::GetAccessControl($Path)
    if (-not $security.AreAccessRulesProtected) {
        throw "Installed hook ACL must disable inherited access rules: $Path"
    }
    $rules = @($security.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    ))
    if ($rules.Count -ne 1) {
        throw "Installed hook ACL must contain exactly one access rule: $Path"
    }
    $rule = $rules[0]
    if (
        $rule.IsInherited -or
        $rule.IdentityReference.Value -cne $currentIdentity -or
        $rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
        $rule.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl
    ) {
        throw "Installed hook ACL must allow only the current user full control: $Path"
    }
}

function Get-FileAclPolicy {
    param([string]$Path)

    $security = [System.IO.File]::GetAccessControl($Path)
    $effectiveRules = @($security.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    ) | ForEach-Object {
        "{0}|{1}|{2}|{3}" -f @(
            $_.IdentityReference.Value,
            [int]$_.AccessControlType,
            [int]$_.FileSystemRights,
            [bool]$_.IsInherited
        )
    } | Sort-Object)
    return [pscustomobject]@{
        Protected = $security.AreAccessRulesProtected
        Owner = $security.GetOwner([System.Security.Principal.SecurityIdentifier])
        ExplicitRules = @($security.GetAccessRules(
            $true,
            $false,
            [System.Security.Principal.SecurityIdentifier]
        ))
        EffectiveRules = $effectiveRules
    }
}

function Restore-FileAclPolicy {
    param(
        [string]$Path,
        [object]$Policy
    )

    $security = New-Object System.Security.AccessControl.FileSecurity
    $security.SetOwner($Policy.Owner)
    $security.SetAccessRuleProtection($Policy.Protected, $false)
    foreach ($rule in @($Policy.ExplicitRules)) {
        [void]$security.AddAccessRule($rule)
    }
    [System.IO.File]::SetAccessControl($Path, $security)
    $actual = Get-FileAclPolicy $Path
    $expectedRules = [string]::Join(";", @($Policy.EffectiveRules))
    $actualRules = [string]::Join(";", @($actual.EffectiveRules))
    if (
        $actual.Protected -ne $Policy.Protected -or
        $actual.Owner.Value -cne $Policy.Owner.Value -or
        $actualRules -cne $expectedRules
    ) {
        throw "File ACL policy could not be restored exactly: $Path"
    }
}

function New-OwnedCopy {
    param(
        [string]$Source,
        [string]$Destination
    )

    $sourceStream = $null
    $destinationStream = $null
    $sha256 = $null
    $createdDestination = $false
    $createdIdentity = $null
    $completedCopy = $false
    $copyHash = $null
    $copyLength = 0
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
        $createdIdentity = [HookInstaller.NativeFileIdentity]::FromHandle(
            $destinationStream.SafeFileHandle
        )
        Set-RestrictedFileAcl $Destination
        Assert-RestrictedFileAcl $Destination
        $sourceStream = New-Object System.IO.FileStream(
            $Source,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read,
            65536,
            [System.IO.FileOptions]::SequentialScan
        )
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        [byte[]]$buffer = New-Object byte[] 65536
        while (($bytesRead = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $destinationStream.Write($buffer, 0, $bytesRead)
            [void]$sha256.TransformBlock($buffer, 0, $bytesRead, $buffer, 0)
        }
        [void]$sha256.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        $destinationStream.Flush($true)
        $copyHash = [System.BitConverter]::ToString($sha256.Hash).Replace("-", "")
        $copyLength = $destinationStream.Length
        $completedCopy = $true
    }
    finally {
        if ($null -ne $sourceStream) {
            $sourceStream.Dispose()
        }
        if ($null -ne $sha256) {
            $sha256.Dispose()
        }
        if ($null -ne $destinationStream) {
            $destinationStream.Dispose()
        }
        if (
            $createdDestination -and
            -not $completedCopy -and
            [System.IO.File]::Exists($Destination)
        ) {
            $partialRecord = Get-OwnedFileRecord $Destination
            if ($partialRecord.Identity -cne $createdIdentity) {
                throw "Owned temporary identity changed during failed copy; preserved: $Destination"
            }
            Remove-OwnedFile $partialRecord "failed copy temporary"
        }
    }
    return [pscustomobject]@{
        Path = $Destination
        Hash = $copyHash
        Length = $copyLength
        Identity = $createdIdentity
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

function Get-OwnedFileRecord {
    param([string]$Path)

    Assert-RegularDestination $Path
    if (-not [System.IO.File]::Exists($Path)) {
        throw "Owned file is missing: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    return [pscustomobject]@{
        Path = [System.IO.Path]::GetFullPath($Path)
        Hash = Get-FileHashHex $Path
        Length = $item.Length
        Identity = [HookInstaller.NativeFileIdentity]::FromPath($Path)
    }
}

function Test-OwnedFileRecord {
    param([object]$Record)

    if ($null -eq $Record -or -not [System.IO.File]::Exists($Record.Path)) {
        return $false
    }
    try {
        $current = Get-OwnedFileRecord $Record.Path
        return (
            $current.Identity -ceq $Record.Identity -and
            $current.Length -eq $Record.Length -and
            $current.Hash -ceq $Record.Hash
        )
    }
    catch {
        return $false
    }
}

function Remove-OwnedFile {
    param(
        [object]$Record,
        [string]$Description
    )

    if (-not (Test-OwnedFileRecord $Record)) {
        throw "$Description changed identity or content; preserved: $($Record.Path)"
    }
    [System.IO.File]::Delete($Record.Path)
}

function Test-FileRecordsEqual {
    param(
        [object]$First,
        [object]$Second
    )

    return (
        $null -ne $First -and
        $null -ne $Second -and
        $First.Identity -ceq $Second.Identity -and
        $First.Length -eq $Second.Length -and
        $First.Hash -ceq $Second.Hash
    )
}

function New-UniqueChildPath {
    param(
        [string]$Directory,
        [string]$Prefix,
        [string]$Suffix,
        [System.Collections.Generic.Queue[string]]$CandidateNames = $null
    )

    for ($attempt = 0; $attempt -lt 16; $attempt++) {
        if ($null -ne $CandidateNames) {
            if ($CandidateNames.Count -eq 0) {
                throw "Controlled candidate names were exhausted without a safe unused path."
            }
            $candidateName = $CandidateNames.Dequeue()
            if (
                [System.IO.Path]::GetFileName($candidateName) -cne $candidateName -or
                -not $candidateName.StartsWith($Prefix, [System.StringComparison]::Ordinal) -or
                -not $candidateName.EndsWith($Suffix, [System.StringComparison]::Ordinal)
            ) {
                throw "Controlled candidate name must match the required direct-child prefix and suffix."
            }
        }
        else {
            $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss-fff")
            $token = [Guid]::NewGuid().ToString("N")
            $candidateName = "$Prefix$stamp-$token$Suffix"
        }
        $candidate = Join-Path $Directory $candidateName
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
        [object]$InstalledRecord,
        [object]$OriginalAclPolicy = $null,
        [scriptblock]$BeforeRollbackReplaceAction = $null
    )

    Assert-RegularDestination $Destination
    if (-not (Test-OwnedFileRecord $InstalledRecord)) {
        throw "Cannot roll back because the installed hook changed concurrently: $Destination"
    }
    if ($null -ne $BeforeRollbackReplaceAction) {
        & $BeforeRollbackReplaceAction $Destination
    }
    if ($HadDestination) {
        if (-not [System.IO.File]::Exists($Backup)) {
            throw "Cannot roll back because the backup is missing: $Backup"
        }
        $rollbackTemporary = New-UniqueChildPath $Directory "pre-commit.installing-rollback-" ".tmp"
        $rollbackDisplaced = New-UniqueChildPath $Directory "pre-commit.installing-displaced-" ".tmp"
        $rollbackRecord = $null
        $displacedRecord = $null
        try {
            $rollbackRecord = New-OwnedCopy $Backup $rollbackTemporary
            [System.IO.File]::Replace(
                $rollbackTemporary,
                $Destination,
                $rollbackDisplaced,
                $true
            )
            $rollbackRecord = $null
            $displacedRecord = Get-OwnedFileRecord $rollbackDisplaced
            if (-not (Test-FileRecordsEqual $displacedRecord $InstalledRecord)) {
                $concurrentAclPolicy = Get-FileAclPolicy $rollbackDisplaced
                $recoveryArtifact = New-UniqueChildPath $Directory "pre-commit.recovery-" ".bak"
                [System.IO.File]::Replace(
                    $rollbackDisplaced,
                    $Destination,
                    $recoveryArtifact,
                    $true
                )
                $displacedRecord = $null
                Restore-FileAclPolicy $Destination $concurrentAclPolicy
                throw (
                    "Concurrent hook content was preserved at the destination; " +
                    "the prior hook also remains in backup and recovery artifacts."
                )
            }
            Remove-OwnedFile $displacedRecord "rollback displaced installed hook"
            $displacedRecord = $null
            Restore-FileAclPolicy $Destination $OriginalAclPolicy
        }
        finally {
            if ($null -ne $rollbackRecord -and [System.IO.File]::Exists($rollbackRecord.Path)) {
                Remove-OwnedFile $rollbackRecord "rollback temporary"
            }
            if ($null -ne $displacedRecord -and [System.IO.File]::Exists($displacedRecord.Path)) {
                Remove-OwnedFile $displacedRecord "rollback displaced file"
            }
        }
    }
    else {
        Remove-OwnedFile $InstalledRecord "newly installed hook"
    }
}

function Invoke-HookInstaller {
    param(
        [string]$HookDirectory = "",
        [System.Collections.Generic.Queue[string]]$CandidateNames = $null,
        [scriptblock]$RepositoryOptInAction = $null,
        [scriptblock]$BeforeRollbackReplaceAction = $null
    )

    $rootOutput = @(& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or $rootOutput.Count -ne 1) {
        throw "Could not resolve exactly one repository root with Git."
    }
    $repositoryRoot = Assert-ExistingPathWithoutReparse $rootOutput[0] "Repository root"
    if (-not [System.IO.Directory]::Exists($repositoryRoot)) {
        throw "Git repository root is not a directory: $repositoryRoot"
    }

    $expectedScript = Join-Path (Join-Path $repositoryRoot "scripts") "install-global-hook.ps1"
    $actualScript = $script:InstallerScriptPath
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
    $originalAclPolicy = $null
    if ($hadDestination) {
        $originalAclPolicy = Get-FileAclPolicy $destination
    }
    $backup = $null
    if ($hadDestination) {
        $backup = New-UniqueChildPath $directory "pre-commit.backup-" ".bak" $CandidateNames
        Assert-DirectChild $directory $backup "Hook backup"
    }
    $temporary = New-UniqueChildPath $directory "pre-commit.installing-" ".tmp" $CandidateNames
    Assert-DirectChild $directory $temporary "Hook temporary file"

    $ownedTemporary = $null
    $installed = $false
    $installedRecord = $null
    try {
        $ownedTemporary = New-OwnedCopy $source $temporary
        Assert-RegularDestination $destination
        if ($hadDestination) {
            [System.IO.File]::Replace($temporary, $destination, $backup, $true)
        }
        else {
            [System.IO.File]::Move($temporary, $destination)
        }
        $ownedTemporary = $null
        $installed = $true
        $installedRecord = Get-OwnedFileRecord $destination
        Set-RestrictedFileAcl $destination
        Assert-RestrictedFileAcl $destination
        $installedRecord = Get-OwnedFileRecord $destination

        if ($null -ne $RepositoryOptInAction) {
            & $RepositoryOptInAction
        }
        $configOutput = @(& git config --local --replace-all workflow.useRepositoryHook true 2>&1)
        $configExit = $LASTEXITCODE
        if ($configExit -ne 0) {
            $detail = [string]::Join([System.Environment]::NewLine, @($configOutput | ForEach-Object { [string]$_ }))
            throw "Failed to atomically set the repository opt-in with local Git config. $detail"
        }
    }
    catch {
        $primaryFailure = $_.Exception.Message
        if ($installed) {
            try {
                Restore-InstalledHook `
                    $directory `
                    $destination `
                    $backup `
                    $hadDestination `
                    $installedRecord `
                    $originalAclPolicy `
                    $BeforeRollbackReplaceAction
            }
            catch {
                throw "$primaryFailure Rollback also failed: $($_.Exception.Message)"
            }
        }
        throw $primaryFailure
    }
    finally {
        if ($null -ne $ownedTemporary -and [System.IO.File]::Exists($ownedTemporary.Path)) {
            Remove-OwnedFile $ownedTemporary "installation temporary"
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
    Write-Host "Opt-out: git config --local --unset-all workflow.useRepositoryHook"
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-HookInstaller -HookDirectory $HookDirectory
    }
    catch {
        Write-Failure $_.Exception.Message
        exit 1
    }
}
