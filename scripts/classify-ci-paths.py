#!/usr/bin/env python3
"""Classify changed repository paths for path-aware CI routing."""

from __future__ import annotations

import argparse
import ctypes
import errno
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

DOC_SUFFIXES = {".md", ".txt", ".rst"}
SHARED_EXACT = {
    ".github/workflows/ci.yml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/micro-task-template.md",
    "pytest.ini",
    "requirements.txt",
    "scripts/classify-ci-paths.py",
    "scripts/verify-fast.ps1",
    "scripts/verify-before-commit.ps1",
    "scripts/verify-staged.ps1",
}
POLICY_PREFIXES = (
    "docs/superpowers/specs/2026-07-29-micro-task-fast-lane",
    "docs/superpowers/plans/2026-07-29-micro-task-fast-lane",
)
BACKEND_PREFIXES = ("app/", "tests/")
FRONTEND_PREFIXES = ("frontend/",)
FULL_CI = {"backend": True, "frontend": True, "docs_only": False}


def classify_paths(paths: list[str], force_full: bool = False) -> dict[str, bool]:
    """Return the required CI jobs, defaulting uncertain inputs to full CI."""
    if force_full:
        return FULL_CI.copy()

    normalized_paths = [raw_path.replace("\\", "/") for raw_path in paths]
    if not normalized_paths or any(
        not _is_repository_relative_path(path) for path in normalized_paths
    ):
        return FULL_CI.copy()

    backend = False
    frontend = False
    docs_only = True
    for path in normalized_paths:
        if (
            path in SHARED_EXACT
            or path.startswith(".github/")
            or path.startswith(POLICY_PREFIXES)
        ):
            backend = frontend = True
            docs_only = False
        elif path.startswith(BACKEND_PREFIXES) or (
            path.startswith("scripts/") and path.endswith((".py", ".ps1", ".sh"))
        ):
            backend = True
            docs_only = False
        elif path.startswith(FRONTEND_PREFIXES):
            frontend = True
            docs_only = False
        elif Path(path).suffix.lower() not in DOC_SUFFIXES:
            backend = frontend = True
            docs_only = False

    return {"backend": backend, "frontend": frontend, "docs_only": docs_only}


def _is_repository_relative_path(path: str) -> bool:
    if not path or path.startswith("/") or "\0" in path:
        return False
    if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
        return False
    return all(component not in {"", ".", ".."} for component in path.split("/"))


def read_zero_paths(stream: BinaryIO) -> list[str]:
    """Read strict UTF-8 paths from terminal-NUL-delimited input."""
    payload = stream.read()
    chunks = payload.split(b"\0")
    if chunks[-1] != b"":
        raise ValueError("NUL-delimited input must end with NUL")
    return [chunk.decode("utf-8", errors="strict") for chunk in chunks[:-1]]


def write_outputs(path: Path, values: dict[str, bool]) -> None:
    """Atomically append a complete payload while preserving prior output."""
    path = Path(os.path.abspath(path))
    lines = [f"{name}={'true' if value else 'false'}" for name, value in values.items()]
    payload = ("\n".join(lines) + "\n").encode("utf-8")

    parent_chain = _capture_parent_chain(path)
    existing, existing_identity, existing_mode = _read_existing_output(path)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    temporary_object_identity: tuple[int, int] | None = None
    try:
        temporary_object_identity = _directory_identity(os.fstat(descriptor))
        temporary_stream = os.fdopen(descriptor, "wb", buffering=0)
        descriptor = -1
        with temporary_stream:
            _write_all(temporary_stream, existing + payload)
            temporary_stream.flush()
            os.fsync(temporary_stream.fileno())
            temporary_identity = _file_identity(os.fstat(temporary_stream.fileno()))
        if existing_mode is not None:
            os.chmod(temporary_path, existing_mode)
        _revalidate_parent_chain(parent_chain)
        _revalidate_target(path, existing_identity)
        _revalidate_temporary(temporary_path, temporary_identity)
        _commit_candidate(
            path,
            temporary_path,
            temporary_identity,
            existing_identity,
            parent_chain,
        )
    finally:
        try:
            if descriptor >= 0:
                os.close(descriptor)
        finally:
            if temporary_object_identity is None:
                # Without a handle-bound identity, a pathname delete could remove
                # a concurrently substituted object. Preserve the unknown artifact.
                pass
            else:
                _cleanup_temporary(temporary_path, temporary_object_identity)


def _commit_candidate(
    target: Path,
    candidate: Path,
    candidate_identity: tuple[int, int, int, int],
    expected_target_identity: tuple[int, int, int, int] | None,
    parent_chain: tuple[tuple[Path, tuple[int, int]], ...],
) -> None:
    placeholder_identity: tuple[int, int, int, int] | None = None
    placeholder_object_identity: tuple[int, int] | None = None
    commit_target_identity = expected_target_identity
    if commit_target_identity is None:
        placeholder_identity = _create_placeholder(target)
        placeholder_object_identity = placeholder_identity[:2]
        commit_target_identity = placeholder_identity

    try:
        _revalidate_parent_chain(parent_chain)
        _revalidate_target(target, commit_target_identity)
        _revalidate_temporary(candidate, candidate_identity)
        displaced = _atomic_exchange(candidate, target)
    except BaseException:
        if placeholder_object_identity is not None:
            _remove_if_same_object(target, placeholder_object_identity)
        raise

    displaced_object_identity: tuple[int, int] | None = None
    try:
        displaced_info = displaced.lstat()
        displaced_object_identity = _directory_identity(displaced_info)
        published_info = target.lstat()
        _require_safe_kind(published_info, target, directory=False)
        if _file_identity(published_info) != candidate_identity:
            raise OSError(f"Unverified GitHub output was published: {target}")
        _require_safe_kind(displaced_info, displaced, directory=False)
        if _file_identity(displaced_info) != commit_target_identity:
            raise OSError(f"GitHub output changed at atomic commit: {target}")
    except BaseException as validation_error:
        if displaced_object_identity is None:
            raise OSError(
                f"GitHub output displaced object vanished after atomic commit: {target}"
            ) from validation_error
        _rollback_exchange(
            target,
            displaced,
            displaced_object_identity,
            candidate_identity[:2],
            placeholder_object_identity,
            validation_error,
        )

    _cleanup_temporary(displaced, commit_target_identity[:2])
    _remove_empty_exchange_container(displaced, target.parent)


def _rollback_exchange(
    target: Path,
    displaced: Path,
    displaced_object_identity: tuple[int, int],
    candidate_object_identity: tuple[int, int],
    placeholder_object_identity: tuple[int, int] | None,
    validation_error: BaseException,
) -> None:
    try:
        rejected = _atomic_exchange(displaced, target)
        restored = target.lstat()
        if _directory_identity(restored) != displaced_object_identity:
            raise OSError(f"GitHub output rollback restored the wrong object: {target}")
        if _remove_if_same_object(rejected, candidate_object_identity):
            _remove_empty_exchange_container(rejected, target.parent)
        if placeholder_object_identity is not None:
            _remove_if_same_object(target, placeholder_object_identity)
        _remove_empty_exchange_container(displaced, target.parent)
    except BaseException as rollback_error:
        raise OSError(
            f"GitHub output atomic validation failed and rollback failed: {target}"
        ) from rollback_error
    raise OSError(
        f"GitHub output changed during atomic commit: {target}"
    ) from validation_error


def _create_placeholder(path: Path) -> tuple[int, int, int, int]:
    flags = (
        os.O_CREAT
        | os.O_EXCL
        | os.O_WRONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        _require_safe_kind(info, path, directory=False)
        os.fsync(descriptor)
        return _file_identity(info)
    finally:
        os.close(descriptor)


def _atomic_exchange(source: Path, target: Path) -> Path:
    if os.name == "nt":
        return _windows_exchange(source, target)
    if sys.platform.startswith("linux"):
        return _linux_exchange(source, target)
    raise OSError(
        errno.ENOTSUP,
        "atomic GitHub output exchange is unsupported on this platform",
    )


def _linux_exchange(source: Path, target: Path) -> Path:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOTSUP, "renameat2 is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_exchange = 0x2
    result = renameat2(
        at_fdcwd,
        os.fsencode(source),
        at_fdcwd,
        os.fsencode(target),
        rename_exchange,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    return source


def _windows_exchange(source: Path, target: Path) -> Path:
    transaction = Path(
        tempfile.mkdtemp(
            dir=target.parent,
            prefix=f".{target.name}.exchange-",
        )
    )
    displaced = transaction / "displaced"
    replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace_file.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    replace_file.restype = ctypes.c_int
    if not replace_file(str(target), str(source), str(displaced), 0, None, None):
        error = ctypes.WinError(ctypes.get_last_error())
        try:
            transaction.rmdir()
        except OSError:
            pass
        raise error
    return displaced


def _capture_parent_chain(path: Path) -> tuple[tuple[Path, tuple[int, int]], ...]:
    chain: list[tuple[Path, tuple[int, int]]] = []
    for parent in reversed((path.parent, *path.parent.parents)):
        try:
            info = parent.lstat()
        except FileNotFoundError as error:
            raise OSError(f"GitHub output parent does not exist: {parent}") from error
        _require_safe_kind(info, parent, directory=True)
        chain.append((parent, _directory_identity(info)))
    return tuple(chain)


def _revalidate_parent_chain(
    chain: tuple[tuple[Path, tuple[int, int]], ...],
) -> None:
    for parent, expected_identity in chain:
        try:
            info = parent.lstat()
        except FileNotFoundError as error:
            raise OSError(f"GitHub output parent changed: {parent}") from error
        _require_safe_kind(info, parent, directory=True)
        if _directory_identity(info) != expected_identity:
            raise OSError(f"GitHub output parent identity changed: {parent}")


def _read_existing_output(
    path: Path,
) -> tuple[bytes, tuple[int, int, int, int] | None, int | None]:
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return b"", None, None
    _require_safe_kind(initial, path, directory=False)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        _require_safe_kind(opened, path, directory=False)
        if _file_identity(opened) != _file_identity(initial):
            raise OSError(f"GitHub output identity changed while opening: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        final = os.fstat(descriptor)
        _require_safe_kind(final, path, directory=False)
        if _file_identity(final) != _file_identity(opened):
            raise OSError(f"GitHub output changed while reading: {path}")
        existing = b"".join(chunks)
        if len(existing) != final.st_size:
            raise OSError(f"GitHub output size changed while reading: {path}")
        return existing, _file_identity(final), stat.S_IMODE(final.st_mode)
    finally:
        os.close(descriptor)


def _revalidate_target(
    path: Path, expected_identity: tuple[int, int, int, int] | None
) -> None:
    try:
        current = path.lstat()
    except FileNotFoundError:
        if expected_identity is None:
            return
        raise OSError(f"GitHub output disappeared before replace: {path}") from None
    _require_safe_kind(current, path, directory=False)
    if expected_identity is None or _file_identity(current) != expected_identity:
        raise OSError(f"GitHub output identity changed before replace: {path}")


def _revalidate_temporary(
    path: Path, expected_identity: tuple[int, int, int, int]
) -> None:
    try:
        current = path.lstat()
    except FileNotFoundError as error:
        raise OSError(f"Temporary GitHub output disappeared: {path}") from error
    _require_safe_kind(current, path, directory=False)
    if _file_identity(current) != expected_identity:
        raise OSError(f"Temporary GitHub output identity changed: {path}")


def _cleanup_temporary(path: Path, expected_identity: tuple[int, int]) -> None:
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    _require_safe_kind(current, path, directory=False)
    if _directory_identity(current) != expected_identity:
        raise OSError(f"Refusing to remove changed temporary GitHub output: {path}")
    path.unlink()


def _remove_if_same_object(path: Path, expected_identity: tuple[int, int]) -> bool:
    try:
        current = path.lstat()
    except FileNotFoundError:
        return False
    if _directory_identity(current) != expected_identity:
        return False
    _require_safe_kind(current, path, directory=False)
    path.unlink()
    return True


def _remove_empty_exchange_container(path: Path, target_parent: Path) -> None:
    if path.parent == target_parent:
        return
    try:
        path.parent.rmdir()
    except OSError:
        pass


def _require_safe_kind(info: os.stat_result, path: Path, *, directory: bool) -> None:
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    file_attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or file_attributes & reparse_attribute:
        raise OSError(f"GitHub output path must not be a link or reparse point: {path}")
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_kind(info.st_mode):
        kind = "directory" if directory else "regular file"
        raise OSError(f"GitHub output path must be a {kind}: {path}")


def _directory_identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _write_all(stream: BinaryIO, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = stream.write(remaining)
        if written is None or written <= 0:
            raise OSError("could not write complete GitHub output")
        remaining = remaining[written:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin-zero", action="store_true", required=True)
    parser.add_argument("--force-full", action="store_true")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        paths = read_zero_paths(sys.stdin.buffer)
    except (UnicodeDecodeError, ValueError) as error:
        print(f"Invalid changed-path input: {error}", file=sys.stderr)
        return 2

    values = classify_paths(paths, force_full=args.force_full)
    write_outputs(args.github_output, values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
