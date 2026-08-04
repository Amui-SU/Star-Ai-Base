"""Contracts for safely installing the repository-aware global Git hook."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from base64 import b64decode, b64encode
from contextlib import contextmanager
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_SOURCE = PROJECT_ROOT / "scripts" / "install-global-hook.ps1"
HOOK_SOURCE = PROJECT_ROOT / "scripts" / "git-hooks" / "pre-commit"
_BASELINE_REPO: tuple[Path, dict[str, str]] | None = None
_INTERNAL_HOST: _PersistentPowerShellHost | None = None

_INTERNAL_HOST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$script:ManagedEnvironmentNames = @()
while (($line = [Console]::In.ReadLine()) -ne $null) {
    if ($line -ceq '__EXIT__') { break }
    $response = $null
    try {
        $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($line))
        $request = $json | ConvertFrom-Json
        foreach ($name in $script:ManagedEnvironmentNames) {
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        }
        $script:ManagedEnvironmentNames = @(
            $request.Environment.PSObject.Properties | ForEach-Object {
                [Environment]::SetEnvironmentVariable($_.Name, [string]$_.Value, 'Process')
                $_.Name
            }
        )
        Set-Location -LiteralPath ([string]$request.WorkingDirectory)
        $block = [ScriptBlock]::Create(
            '. $env:HOOK_INSTALLER_TEST_SCRIPT; ' + [string]$request.Command
        )
        $output = (& $block *>&1 | Out-String)
        $response = @{ Success = $true; Output = $output; Error = '' }
    }
    catch {
        $response = @{
            Success = $false
            Output = ''
            Error = ($_ | Out-String)
        }
    }
    $responseJson = $response | ConvertTo-Json -Compress -Depth 4
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($responseJson))
    [Console]::Out.WriteLine($encoded)
    [Console]::Out.Flush()
}
"""


class _PersistentPowerShellHost:
    def __init__(self, environment: dict[str, str]) -> None:
        command = [_powershell(), "-NoProfile"]
        if Path(command[0]).name.lower().startswith("powershell"):
            command.extend(["-ExecutionPolicy", "Bypass"])
        command.extend(["-Command", _INTERNAL_HOST_SCRIPT])
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    def run(
        self,
        repo: Path,
        environment: dict[str, str],
        command_text: str,
    ) -> subprocess.CompletedProcess[str]:
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        managed_environment = {
            name: value
            for name, value in environment.items()
            if name.startswith("GIT_") or name.startswith("HOOK_INSTALLER_TEST_")
        }
        request = {
            "WorkingDirectory": str(repo),
            "Environment": managed_environment,
            "Command": command_text,
        }
        encoded = b64encode(json.dumps(request).encode("utf-8")).decode("ascii")
        self._process.stdin.write(encoded + "\n")
        self._process.stdin.flush()
        response_line = self._process.stdout.readline()
        if not response_line:
            raise AssertionError("Persistent PowerShell host exited without a response")
        response = json.loads(b64decode(response_line).decode("utf-8"))
        if not response["Success"]:
            raise AssertionError(
                "Persistent PowerShell command failed. "
                f"stdout={response['Output']!r}; stderr={response['Error']!r}"
            )
        return subprocess.CompletedProcess(
            args=["persistent-powershell", command_text],
            returncode=0,
            stdout=response["Output"],
            stderr=response["Error"],
        )

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        assert self._process.stdin is not None
        self._process.stdin.write("__EXIT__\n")
        self._process.stdin.flush()
        self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=5)


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is required for hook installer contract tests")
    return executable


@pytest.fixture(scope="session", autouse=True)
def _installer_repo_baseline(tmp_path_factory: pytest.TempPathFactory):
    global _BASELINE_REPO, _INTERNAL_HOST
    assert INSTALLER_SOURCE.is_file(), "installer has not been implemented"
    assert HOOK_SOURCE.is_file(), "global hook template has not been implemented"
    repo = tmp_path_factory.mktemp("hook-installer-baseline") / "repo"
    environment = init_repo(repo)
    scripts = repo / "scripts"
    (scripts / "git-hooks").mkdir(parents=True)
    shutil.copy2(INSTALLER_SOURCE, scripts / INSTALLER_SOURCE.name)
    shutil.copy2(HOOK_SOURCE, scripts / "git-hooks" / "pre-commit")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    run_command(["git", "add", "--", "scripts", "README.md"], repo, environment)
    run_command(
        ["git", "commit", "--no-verify", "--no-gpg-sign", "-m", "baseline"],
        repo,
        environment,
    )
    _BASELINE_REPO = (repo, environment)
    _INTERNAL_HOST = _PersistentPowerShellHost(environment)
    try:
        yield
    finally:
        _INTERNAL_HOST.close()
        _INTERNAL_HOST = None
        _BASELINE_REPO = None


def _prepare_repo(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    assert _BASELINE_REPO is not None
    baseline, baseline_environment = _BASELINE_REPO
    repo = tmp_path / "repo with 空格"
    shutil.copytree(baseline, repo)
    environment = baseline_environment.copy()
    environment["GIT_CONFIG_GLOBAL"] = str(repo / ".git" / "test-global-config")
    hook_directory = tmp_path / "hooks with 中文"
    hook_directory.mkdir()
    return repo, environment, hook_directory


def _installer_command(repo: Path, hook_directory: Path | None) -> list[str]:
    command = [_powershell(), "-NoProfile"]
    if Path(command[0]).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", str(repo / "scripts" / INSTALLER_SOURCE.name)])
    if hook_directory is not None:
        command.extend(["-HookDirectory", str(hook_directory)])
    return command


def _run_installer(
    repo: Path,
    environment: dict[str, str],
    hook_directory: Path | None,
):
    return run_command(
        _installer_command(repo, hook_directory), repo, environment, timeout=30
    )


def _run_internal(
    repo: Path,
    environment: dict[str, str],
    command_text: str,
):
    assert _INTERNAL_HOST is not None
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_SCRIPT"] = str(
        repo / "scripts" / INSTALLER_SOURCE.name
    )
    return _INTERNAL_HOST.run(repo, internal_environment, command_text)


def _internal_failure(
    repo: Path,
    environment: dict[str, str],
    command_text: str,
) -> str:
    with pytest.raises(AssertionError) as caught:
        _run_internal(repo, environment, command_text)
    return str(caught.value)


def _failure(
    repo: Path,
    environment: dict[str, str],
    hook_directory: Path | None,
) -> str:
    with pytest.raises(AssertionError) as caught:
        _run_installer(repo, environment, hook_directory)
    return str(caught.value)


def _config(repo: Path, environment: dict[str, str], *arguments: str) -> str:
    return run_command(["git", "config", *arguments], repo, environment).stdout.strip()


def _make_junction(link: Path, target: Path, environment: dict[str, str]) -> None:
    if os.name != "nt":
        pytest.skip("junction contracts apply to Windows")
    junction_environment = environment.copy()
    junction_environment["HOOK_INSTALLER_TEST_LINK"] = str(link)
    junction_environment["HOOK_INSTALLER_TEST_TARGET"] = str(target)
    command = [
        _powershell(),
        "-NoProfile",
        "-Command",
        "$ErrorActionPreference='Stop'; New-Item -ItemType Junction "
        "-Path $env:HOOK_INSTALLER_TEST_LINK "
        "-Target $env:HOOK_INSTALLER_TEST_TARGET | Out-Null",
    ]
    run_command(command, link.parent, junction_environment)


def _read_acl(path: Path, repo: Path, environment: dict[str, str]) -> dict[str, object]:
    acl_environment = environment.copy()
    acl_environment["HOOK_INSTALLER_TEST_ACL_PATH"] = str(path)
    result = run_command(
        [
            _powershell(),
            "-NoProfile",
            "-Command",
            "$acl = [System.IO.File]::GetAccessControl($env:HOOK_INSTALLER_TEST_ACL_PATH); "
            "$rules = @($acl.GetAccessRules($true, $true, "
            "[System.Security.Principal.SecurityIdentifier]) | ForEach-Object { "
            "@{ sid = $_.IdentityReference.Value; allow = "
            "($_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow); "
            "rights = [int]$_.FileSystemRights; inherited = $_.IsInherited } }); "
            "@{ protected = $acl.AreAccessRulesProtected; current = "
            "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
            "owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value; "
            "sddl = $acl.GetSecurityDescriptorSddlForm("
            "[System.Security.AccessControl.AccessControlSections]::Access); "
            "rules = $rules } | ConvertTo-Json -Compress -Depth 4",
        ],
        repo,
        acl_environment,
    )
    return json.loads(result.stdout.strip())


def _assert_restricted_acl(payload: dict[str, object]) -> None:
    assert payload["protected"] is True
    assert payload["rules"] == [
        {
            "inherited": False,
            "rights": 2032127,
            "allow": True,
            "sid": payload["current"],
        }
    ]


def test_internal_contracts_reuse_one_isolated_powershell_host(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)

    first = _run_internal(repo, environment, "$PID")
    second = _run_internal(repo, environment, "$PID")

    assert first.stdout.strip() == second.stdout.strip()


@contextmanager
def _exclusive_windows_lock(path: Path):
    if os.name != "nt":
        pytest.skip("exclusive replacement contracts apply to Windows")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_file(str(path), 0x80000000, 0, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        close_handle(handle)


def test_installer_backs_up_exact_bytes_installs_atomically_and_opts_in(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    old_bytes = b"old\x00hook\r\n"
    destination = hook_directory / "pre-commit"
    destination.write_bytes(old_bytes)

    result = _run_installer(repo, environment, hook_directory)

    backups = list(hook_directory.glob("pre-commit.backup-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == old_bytes
    assert destination.read_bytes() == HOOK_SOURCE.read_bytes()
    assert (
        _config(repo, environment, "--local", "--get", "workflow.useRepositoryHook")
        == "true"
    )
    global_config = run_command(
        ["git", "config", "--global", "--list"], repo, environment
    ).stdout
    assert "workflow.userepositoryhook" not in global_config.lower()
    assert f"Installed: {destination.resolve()}" in result.stdout
    assert f"Backup: {backups[0].resolve()}" in result.stdout
    assert "Restore:" in result.stdout
    assert str(backups[0].resolve()) in result.stdout
    assert str(destination.resolve()) in result.stdout
    restore = next(
        line.removeprefix("Restore: ")
        for line in result.stdout.splitlines()
        if line.startswith("Restore: ")
    )
    destination.write_bytes(b"changed after install")
    run_command([_powershell(), "-NoProfile", "-Command", restore], repo, environment)
    assert destination.read_bytes() == old_bytes


def test_existing_hook_final_acl_is_restricted_to_current_user(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"wide inherited hook")
    assert _read_acl(destination, repo, environment)["protected"] is False

    _run_installer(repo, environment, hook_directory)

    _assert_restricted_acl(_read_acl(destination, repo, environment))


def test_multiple_local_opt_in_values_become_one_exact_true(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    for value in ("false", "true"):
        run_command(
            [
                "git",
                "config",
                "--local",
                "--add",
                "workflow.useRepositoryHook",
                value,
            ],
            repo,
            environment,
        )

    _run_installer(repo, environment, hook_directory)

    values = run_command(
        ["git", "config", "--local", "--get-all", "workflow.useRepositoryHook"],
        repo,
        environment,
    ).stdout.splitlines()
    assert values == ["true"]


def test_installer_safely_creates_a_missing_hook_directory(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    hook_directory.rmdir()

    sibling = hook_directory.parent / "must-stay.txt"
    sibling.write_bytes(b"unrelated")

    result = _run_installer(repo, environment, hook_directory)

    assert hook_directory.is_dir()
    destination = hook_directory / "pre-commit"
    assert destination.read_bytes() == HOOK_SOURCE.read_bytes()
    remove_restore = next(
        line.removeprefix("Restore: ")
        for line in result.stdout.splitlines()
        if line.startswith("Restore: ")
    )
    opt_out = next(
        line.removeprefix("Opt-out: ")
        for line in result.stdout.splitlines()
        if line.startswith("Opt-out: ")
    )

    run_command(
        [_powershell(), "-NoProfile", "-Command", remove_restore], repo, environment
    )

    assert not destination.exists()
    assert sibling.read_bytes() == b"unrelated"
    assert (
        _config(repo, environment, "--local", "--get", "workflow.useRepositoryHook")
        == "true"
    )
    run_command([_powershell(), "-NoProfile", "-Command", opt_out], repo, environment)
    with pytest.raises(AssertionError):
        _config(repo, environment, "--local", "--get", "workflow.useRepositoryHook")


def test_owned_temporary_acl_is_protected_and_allows_only_current_user(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "source.bin"
    destination = hook_directory / "pre-commit.installing-acl.tmp"
    source.write_bytes(b"acl contract")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_SOURCE"] = str(source)
    internal_environment["HOOK_INSTALLER_TEST_DESTINATION"] = str(destination)

    result = _run_internal(
        repo,
        internal_environment,
        "$copyHash = New-OwnedCopy "
        "$env:HOOK_INSTALLER_TEST_SOURCE $env:HOOK_INSTALLER_TEST_DESTINATION; "
        "$acl = [System.IO.File]::GetAccessControl($env:HOOK_INSTALLER_TEST_DESTINATION); "
        "$rules = @($acl.GetAccessRules($true, $true, "
        "[System.Security.Principal.SecurityIdentifier]) | ForEach-Object { "
        "@{ sid = $_.IdentityReference.Value; allow = "
        "($_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow); "
        "rights = [int]$_.FileSystemRights; inherited = $_.IsInherited } }); "
        "@{ protected = $acl.AreAccessRulesProtected; current = "
        "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
        "rules = $rules; hash = $copyHash } | ConvertTo-Json -Compress -Depth 4",
    )

    payload = json.loads(result.stdout.strip())
    assert payload["protected"] is True
    assert payload["rules"] == [
        {
            "inherited": False,
            "rights": 2032127,
            "allow": True,
            "sid": payload["current"],
        }
    ]
    assert destination.read_bytes() == b"acl contract"


def test_controlled_candidate_collisions_preserve_existing_files(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    backup_collision = hook_directory / "pre-commit.backup-collision.bak"
    backup_selected = hook_directory / "pre-commit.backup-selected.bak"
    temporary_collision = hook_directory / "pre-commit.installing-collision.tmp"
    temporary_selected = hook_directory / "pre-commit.installing-selected.tmp"
    backup_collision.write_bytes(b"keep backup collision")
    temporary_collision.write_bytes(b"keep temp collision")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    _run_internal(
        repo,
        internal_environment,
        "$candidates = New-Object 'System.Collections.Generic.Queue[string]'; "
        "@('pre-commit.backup-collision.bak','pre-commit.backup-selected.bak',"
        "'pre-commit.installing-collision.tmp','pre-commit.installing-selected.tmp') "
        "| ForEach-Object { $candidates.Enqueue($_) }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-CandidateNames $candidates",
    )

    assert backup_collision.read_bytes() == b"keep backup collision"
    assert temporary_collision.read_bytes() == b"keep temp collision"
    assert backup_selected.read_bytes() == b"old hook"
    assert not temporary_selected.exists()
    assert destination.read_bytes() == HOOK_SOURCE.read_bytes()


def test_backup_collision_after_selection_fails_closed_and_preserves_sentinel(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    backup = hook_directory / "pre-commit.backup-selected.bak"
    destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$candidates = New-Object 'System.Collections.Generic.Queue[string]'; "
        "@('pre-commit.backup-selected.bak',"
        "'pre-commit.installing-selected.tmp') | ForEach-Object { "
        "$candidates.Enqueue($_) }; "
        "$collide = { param($Backup) [System.IO.File]::WriteAllBytes($Backup, "
        "[System.Text.Encoding]::UTF8.GetBytes('backup sentinel')) }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-CandidateNames $candidates -BeforeInstallReplaceAction $collide",
    )

    assert "collision" in failure.lower() or "changed" in failure.lower()
    assert backup.read_bytes() == b"backup sentinel"
    assert destination.read_bytes() == b"old hook"


def test_failure_cleans_only_new_candidates_and_preserves_collisions(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    backup_collision = hook_directory / "pre-commit.backup-collision.bak"
    temporary_collision = hook_directory / "pre-commit.installing-collision.tmp"
    backup_collision.write_bytes(b"keep backup collision")
    temporary_collision.write_bytes(b"keep temp collision")
    (repo / ".git" / "config.lock").write_text("occupied", encoding="utf-8")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    _internal_failure(
        repo,
        internal_environment,
        "$candidates = New-Object 'System.Collections.Generic.Queue[string]'; "
        "@('pre-commit.backup-collision.bak','pre-commit.backup-owned.bak',"
        "'pre-commit.installing-collision.tmp','pre-commit.installing-owned.tmp') "
        "| ForEach-Object { $candidates.Enqueue($_) }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-CandidateNames $candidates",
    )

    assert backup_collision.read_bytes() == b"keep backup collision"
    assert temporary_collision.read_bytes() == b"keep temp collision"
    assert (hook_directory / "pre-commit.backup-owned.bak").read_bytes() == b"old hook"
    assert not (hook_directory / "pre-commit.installing-owned.tmp").exists()
    assert destination.read_bytes() == b"old hook"
    assert set(hook_directory.glob("pre-commit.installing-*")) == {temporary_collision}


@pytest.mark.parametrize(
    "owned_name",
    [
        "pre-commit.installing-owned.tmp",
        "pre-commit.installing-rollback-owned.tmp",
        "pre-commit.installing-displaced-owned.tmp",
    ],
)
def test_owned_cleanup_preserves_a_replaced_path_and_reports_it(
    tmp_path: Path, owned_name: str
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "owned-source.bin"
    owned = hook_directory / owned_name
    source.write_bytes(b"owned bytes")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_SOURCE"] = str(source)
    internal_environment["HOOK_INSTALLER_TEST_OWNED"] = str(owned)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$record = New-OwnedCopy $env:HOOK_INSTALLER_TEST_SOURCE "
        "$env:HOOK_INSTALLER_TEST_OWNED; "
        "[System.IO.File]::WriteAllBytes($env:HOOK_INSTALLER_TEST_OWNED, "
        "[System.Text.Encoding]::UTF8.GetBytes('concurrent replacement')); "
        "Remove-OwnedFile $record 'test owned file'",
    )

    assert "changed" in failure.lower() or "identity" in failure.lower()
    assert owned.read_bytes() == b"concurrent replacement"


def test_owned_cleanup_deletes_the_verified_handle_not_a_replacement_path(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "owned-source.bin"
    owned = hook_directory / "pre-commit.installing-owned.tmp"
    moved = hook_directory / "verified-owned-object.tmp"
    source.write_bytes(b"owned bytes")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_SOURCE"] = str(source)
    internal_environment["HOOK_INSTALLER_TEST_OWNED"] = str(owned)
    internal_environment["HOOK_INSTALLER_TEST_MOVED"] = str(moved)

    _run_internal(
        repo,
        internal_environment,
        "$record = New-OwnedCopy $env:HOOK_INSTALLER_TEST_SOURCE "
        "$env:HOOK_INSTALLER_TEST_OWNED; "
        "$replacePath = { param($Path) "
        "[System.IO.File]::Move($Path, $env:HOOK_INSTALLER_TEST_MOVED); "
        "[System.IO.File]::WriteAllBytes($Path, "
        "[System.Text.Encoding]::UTF8.GetBytes('replacement sentinel')) }; "
        "Remove-OwnedFile $record 'test owned file' "
        "-AfterValidationAction $replacePath",
    )

    assert owned.read_bytes() == b"replacement sentinel"
    assert not moved.exists()


def test_rollback_race_restores_concurrent_destination_and_preserves_artifacts(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$failConfig = { throw 'forced config failure' }; "
        "$race = { param($Destination) [System.IO.File]::WriteAllBytes("
        "$Destination, [System.Text.Encoding]::UTF8.GetBytes('concurrent hook')); "
        "Set-RestrictedFileAcl $Destination }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-RepositoryOptInAction $failConfig -BeforeRollbackReplaceAction $race",
    )

    assert "concurrent" in failure.lower()
    assert destination.read_bytes() == b"concurrent hook"
    _assert_restricted_acl(_read_acl(destination, repo, environment))
    backups = list(hook_directory.glob("pre-commit.backup-*.bak"))
    recoveries = list(hook_directory.glob("pre-commit.recovery-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old hook"
    assert len(recoveries) == 1
    assert recoveries[0].read_bytes() == b"old hook"
    assert not list(hook_directory.glob("pre-commit.installing-*"))


def test_recovery_collision_after_selection_preserves_sentinel_and_concurrent_hook(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$failConfig = { throw 'forced config failure' }; "
        "$race = { param($Destination) [System.IO.File]::WriteAllBytes("
        "$Destination, [System.Text.Encoding]::UTF8.GetBytes('concurrent hook')) }; "
        "$script:recoveryCollided = $false; "
        "$collideOnce = { param($Recovery) if (-not $script:recoveryCollided) { "
        "$script:recoveryCollided = $true; [System.IO.File]::WriteAllBytes("
        "$Recovery, [System.Text.Encoding]::UTF8.GetBytes('recovery sentinel')) } }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-RepositoryOptInAction $failConfig -BeforeRollbackReplaceAction $race "
        "-BeforeRecoveryReplaceAction $collideOnce",
    )

    assert "concurrent" in failure.lower()
    assert destination.read_bytes() == b"concurrent hook"
    recovery_contents = {
        path.read_bytes() for path in hook_directory.glob("pre-commit.recovery-*.bak")
    }
    assert recovery_contents == {b"recovery sentinel", b"old hook"}


def test_rollback_displaced_collision_preserves_sentinel_and_restores_old_hook(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$failConfig = { throw 'forced config failure' }; "
        "$script:rollbackCollided = $false; "
        "$collideOnce = { param($Displaced) if (-not $script:rollbackCollided) { "
        "$script:rollbackCollided = $true; [System.IO.File]::WriteAllBytes("
        "$Displaced, [System.Text.Encoding]::UTF8.GetBytes('rollback sentinel')) } }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-RepositoryOptInAction $failConfig "
        "-BeforeRollbackArtifactReplaceAction $collideOnce",
    )

    assert "forced config failure" in failure
    assert destination.read_bytes() == b"old hook"
    displaced_contents = {
        path.read_bytes()
        for path in hook_directory.glob("pre-commit.installing-displaced-*.tmp")
    }
    assert displaced_contents == {b"rollback sentinel"}


@pytest.mark.parametrize("had_destination", [False, True])
def test_source_change_after_copy_does_not_break_config_failure_rollback(
    tmp_path: Path, had_destination: bool
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "scripts" / "git-hooks" / "pre-commit"
    original_source = source.read_bytes()
    changed_source = b"changed after atomic installation"
    destination = hook_directory / "pre-commit"
    if had_destination:
        destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)
    internal_environment["HOOK_INSTALLER_TEST_SOURCE"] = str(source)
    internal_environment["HOOK_INSTALLER_TEST_CHANGED_SOURCE"] = changed_source.decode()

    failure = _internal_failure(
        repo,
        internal_environment,
        "$script:forbiddenSource = [System.IO.Path]::GetFullPath("
        "$env:HOOK_INSTALLER_TEST_SOURCE); "
        "$script:originalHash = (Get-Item Function:Get-FileHashHex).ScriptBlock; "
        "function Get-FileHashHex { param([string]$Path) "
        "if ([System.IO.Path]::GetFullPath($Path).Equals($script:forbiddenSource, "
        "[System.StringComparison]::OrdinalIgnoreCase)) { "
        "throw 'installed hash must not reread source' }; "
        "& $script:originalHash $Path }; "
        "$failConfig = { [System.IO.File]::WriteAllBytes("
        "$env:HOOK_INSTALLER_TEST_SOURCE, [System.Text.Encoding]::UTF8.GetBytes("
        "$env:HOOK_INSTALLER_TEST_CHANGED_SOURCE)); throw 'forced local config failure' }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-RepositoryOptInAction $failConfig",
    )

    assert "forced local config failure" in failure
    assert source.read_bytes() == changed_source
    assert source.read_bytes() != original_source
    if had_destination:
        assert destination.read_bytes() == b"old hook"
    else:
        assert not destination.exists()
    assert not list(hook_directory.glob("pre-commit.installing-*"))


def test_copy_hash_describes_written_bytes_after_source_changes(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "copy-source.bin"
    destination = hook_directory / "pre-commit.installing-hash.tmp"
    source.write_bytes(b"copied bytes")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_SOURCE"] = str(source)
    internal_environment["HOOK_INSTALLER_TEST_DESTINATION"] = str(destination)

    result = _run_internal(
        repo,
        internal_environment,
        "$copyHash = New-OwnedCopy $env:HOOK_INSTALLER_TEST_SOURCE "
        "$env:HOOK_INSTALLER_TEST_DESTINATION; "
        "[System.IO.File]::WriteAllBytes($env:HOOK_INSTALLER_TEST_SOURCE, "
        "[System.Text.Encoding]::UTF8.GetBytes('changed source')); "
        "@{ copy = $copyHash.Hash; destination = "
        "(Get-FileHashHex $env:HOOK_INSTALLER_TEST_DESTINATION); source = "
        "(Get-FileHashHex $env:HOOK_INSTALLER_TEST_SOURCE) } "
        "| ConvertTo-Json -Compress",
    )

    hashes = json.loads(result.stdout.strip())
    assert hashes["copy"] == hashes["destination"]
    assert hashes["copy"] != hashes["source"]


def test_volume_root_normalization_preserves_the_root_separator(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)

    result = _run_internal(
        repo,
        environment,
        "$root = [System.IO.Path]::GetPathRoot($env:TEMP); "
        "$normalized = Get-NormalizedAbsolutePath $root 'Volume root'; "
        "$checked = Assert-ExistingPathWithoutReparse $root 'Volume root'; "
        "@{ root = $root; normalized = $normalized; checked = $checked } "
        "| ConvertTo-Json -Compress",
    )

    paths = json.loads(result.stdout.strip())
    assert paths["normalized"] == paths["root"]
    assert paths["checked"] == paths["root"]


def test_source_read_failure_removes_only_its_owned_temporary_file(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source = repo / "scripts" / "git-hooks" / "pre-commit"
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")

    with _exclusive_windows_lock(source):
        _failure(repo, environment, hook_directory)

    assert destination.read_bytes() == b"old hook"
    assert not list(hook_directory.glob("pre-commit.installing-*"))
    assert not list(hook_directory.glob("pre-commit.backup-*.bak"))


def test_atomic_replace_failure_preserves_destination_and_cleans_temporary(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"locked old hook")

    with _exclusive_windows_lock(destination):
        _failure(repo, environment, hook_directory)

    assert destination.read_bytes() == b"locked old hook"
    assert not list(hook_directory.glob("pre-commit.installing-*"))
    assert not list(hook_directory.glob("pre-commit.backup-*.bak"))


def test_injected_absolute_escape_path_is_rejected(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    escaped = hook_directory.parent / hook_directory.name / ".." / "escape-hooks"

    failure = _failure(repo, environment, escaped)

    assert "unsafe" in failure.lower()
    assert not (tmp_path / "escape-hooks").exists()


def test_installer_is_idempotent_and_never_overwrites_older_backups(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"original")
    sentinel = hook_directory / "pre-commit.backup-20000101-000000-000.bak"
    sentinel.write_bytes(b"sentinel")

    _run_installer(repo, environment, hook_directory)
    first_backups = set(hook_directory.glob("pre-commit.backup-*.bak"))
    _run_installer(repo, environment, hook_directory)
    second_backups = set(hook_directory.glob("pre-commit.backup-*.bak"))

    assert sentinel.read_bytes() == b"sentinel"
    assert len(first_backups) == 2
    assert len(second_backups) == 3
    assert all(path.is_file() for path in second_backups)
    assert destination.read_bytes() == HOOK_SOURCE.read_bytes()


@pytest.mark.parametrize(
    "configured", ["relative-hooks", "../escape", "hooks/../escape"]
)
def test_global_hook_path_must_be_absolute(tmp_path: Path, configured: str) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)
    run_command(
        ["git", "config", "--global", "--add", "core.hooksPath", configured],
        repo,
        environment,
    )

    failure = _failure(repo, environment, None)

    assert "absolute" in failure.lower() or "unsafe" in failure.lower()


def test_global_hook_path_must_have_exactly_one_value(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    other = tmp_path / "other-hooks"
    other.mkdir()
    for configured in (hook_directory, other):
        run_command(
            ["git", "config", "--global", "--add", "core.hooksPath", str(configured)],
            repo,
            environment,
        )

    failure = _failure(repo, environment, None)

    assert "exactly one" in failure.lower() or "multiple" in failure.lower()


def test_missing_global_hook_path_fails_closed(tmp_path: Path) -> None:
    repo, environment, _ = _prepare_repo(tmp_path)

    failure = _failure(repo, environment, None)

    assert "core.hookspath" in failure.lower()


def test_existing_hook_destination_cannot_be_a_directory(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    (hook_directory / "pre-commit").mkdir()

    failure = _failure(repo, environment, hook_directory)

    assert "destination" in failure.lower()


def test_reparse_hook_directory_is_rejected(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    real_directory = tmp_path / "real-hooks"
    real_directory.mkdir()
    hook_directory.rmdir()
    _make_junction(hook_directory, real_directory, environment)

    failure = _failure(repo, environment, hook_directory)

    assert "reparse" in failure.lower()
    assert not (real_directory / "pre-commit").exists()


def test_reparse_hook_directory_ancestor_is_rejected(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    hook_directory.rmdir()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    _make_junction(linked_parent, real_parent, environment)
    nested = linked_parent / "hooks"

    failure = _failure(repo, environment, nested)

    assert "reparse" in failure.lower()
    assert not (real_parent / "hooks").exists()


def test_git_symlink_source_is_rejected(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    source_relative = "scripts/git-hooks/pre-commit"
    # Replace the index entry with Git symlink mode while leaving a readable file on disk.
    object_id = run_command(
        ["git", "hash-object", source_relative], repo, environment
    ).stdout.strip()
    run_command(
        ["git", "update-index", "--cacheinfo", f"120000,{object_id},{source_relative}"],
        repo,
        environment,
    )
    failure = _failure(repo, environment, hook_directory)

    assert "symbolic" in failure.lower() or "120000" in failure.lower()
    assert not (hook_directory / "pre-commit").exists()


def test_reparse_source_ancestor_is_rejected(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    original_scripts = repo / "scripts"
    real_scripts = repo / "real-scripts"
    original_scripts.rename(real_scripts)
    _make_junction(original_scripts, real_scripts, environment)

    failure = _failure(repo, environment, hook_directory)

    assert "reparse" in failure.lower()
    assert not (hook_directory / "pre-commit").exists()


def test_existing_destination_reparse_point_is_rejected(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("destination reparse contract applies to Windows")
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    target = tmp_path / "target-hook"
    target.write_text("untouched", encoding="utf-8")
    destination = hook_directory / "pre-commit"
    try:
        os.symlink(target, destination)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    failure = _failure(repo, environment, hook_directory)

    assert "reparse" in failure.lower() or "link" in failure.lower()
    assert target.read_text(encoding="utf-8") == "untouched"


def test_rollback_restores_acl_captured_from_the_actual_displaced_backup(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    destination.write_bytes(b"old hook")
    internal_environment = environment.copy()
    internal_environment["HOOK_INSTALLER_TEST_DIRECTORY"] = str(hook_directory)
    internal_environment["HOOK_INSTALLER_TEST_DESTINATION"] = str(destination)

    failure = _internal_failure(
        repo,
        internal_environment,
        "$changeDisplacedAcl = { param($Backup) "
        "Set-RestrictedFileAcl $env:HOOK_INSTALLER_TEST_DESTINATION }; "
        "$failConfig = { throw 'forced config failure' }; "
        "Invoke-HookInstaller -HookDirectory $env:HOOK_INSTALLER_TEST_DIRECTORY "
        "-BeforeInstallReplaceAction $changeDisplacedAcl "
        "-RepositoryOptInAction $failConfig",
    )

    assert "forced config failure" in failure
    assert destination.read_bytes() == b"old hook"
    _assert_restricted_acl(_read_acl(destination, repo, environment))
    backups = list(hook_directory.glob("pre-commit.backup-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old hook"
    _assert_restricted_acl(_read_acl(backups[0], repo, environment))


def test_config_failure_restores_old_hook_and_keeps_diagnostic_backup(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    old_bytes = b"old hook"
    destination.write_bytes(old_bytes)
    original_acl = _read_acl(destination, repo, environment)
    (repo / ".git" / "config.lock").write_text("occupied", encoding="utf-8")

    failure = _failure(repo, environment, hook_directory)
    assert "opt-in" in failure.lower() or "config" in failure.lower()
    assert destination.read_bytes() == old_bytes
    restored_acl = _read_acl(destination, repo, environment)
    assert restored_acl["owner"] == original_acl["owner"]
    assert restored_acl["protected"] == original_acl["protected"]
    assert restored_acl["rules"] == original_acl["rules"]
    backups = list(hook_directory.glob("pre-commit.backup-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == old_bytes
    assert not list(hook_directory.glob("pre-commit.installing-*"))


def test_config_failure_removes_a_newly_installed_hook(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    (repo / ".git" / "config.lock").write_text("occupied", encoding="utf-8")

    _failure(repo, environment, hook_directory)

    assert not (hook_directory / "pre-commit").exists()
    assert not list(hook_directory.glob("pre-commit.installing-*"))


def test_installer_source_has_ps51_main_guard_and_no_recursive_cleanup() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")

    assert source.startswith("#requires -Version 5.1")
    assert "$MyInvocation.InvocationName -ne '.'" in source
    assert "Remove-Item -Recurse" not in source
    assert "git config --local --replace-all workflow.useRepositoryHook true" in source
