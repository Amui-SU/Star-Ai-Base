"""Contracts for safely installing the repository-aware global Git hook."""

from __future__ import annotations

import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

from .support import init_repo, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_SOURCE = PROJECT_ROOT / "scripts" / "install-global-hook.ps1"
HOOK_SOURCE = PROJECT_ROOT / "scripts" / "git-hooks" / "pre-commit"


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is required for hook installer contract tests")
    return executable


def _prepare_repo(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    assert INSTALLER_SOURCE.is_file(), "installer has not been implemented"
    assert HOOK_SOURCE.is_file(), "global hook template has not been implemented"
    repo = tmp_path / "repo with 空格"
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


def test_installer_safely_creates_a_missing_hook_directory(tmp_path: Path) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    hook_directory.rmdir()

    _run_installer(repo, environment, hook_directory)

    assert hook_directory.is_dir()
    assert (hook_directory / "pre-commit").read_bytes() == HOOK_SOURCE.read_bytes()


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


def test_config_failure_restores_old_hook_and_keeps_diagnostic_backup(
    tmp_path: Path,
) -> None:
    repo, environment, hook_directory = _prepare_repo(tmp_path)
    destination = hook_directory / "pre-commit"
    old_bytes = b"old hook"
    destination.write_bytes(old_bytes)
    (repo / ".git" / "config.lock").write_text("occupied", encoding="utf-8")

    failure = _failure(repo, environment, hook_directory)
    assert "opt-in" in failure.lower() or "config" in failure.lower()
    assert destination.read_bytes() == old_bytes
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


def test_installer_source_has_ps51_atomic_and_collision_safe_primitives() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")

    assert source.startswith("#requires -Version 5.1")
    assert "[System.IO.FileMode]::CreateNew" in source
    assert "[System.IO.File]::Replace" in source
    assert "[System.IO.File]::Move" in source
    assert "Flush($true)" in source
    assert re.search(r"GetAccessControl|FileSecurity", source)
    assert "Remove-Item -Recurse" not in source
    assert "git config --local workflow.useRepositoryHook true" in source
