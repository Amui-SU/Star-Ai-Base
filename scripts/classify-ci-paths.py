#!/usr/bin/env python3
"""Classify changed repository paths for path-aware CI routing."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

DOCS_ONLY_PATHS = {"README.md"}
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
    "docs/security/",
    "docs/deployment/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/2026-07-29-micro-task-fast-lane",
)
BACKEND_EXACT = {"requirements-dev.txt"}
BACKEND_POLICY_PREFIXES = ("docs/superpowers/plans/",)
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
        elif path in BACKEND_EXACT or path.startswith(BACKEND_POLICY_PREFIXES):
            backend = True
            docs_only = False
        elif path.startswith(BACKEND_PREFIXES) or (
            path.startswith("scripts/") and path.endswith((".py", ".ps1", ".sh"))
        ):
            backend = True
            docs_only = False
        elif path.startswith(FRONTEND_PREFIXES):
            frontend = True
            docs_only = False
        elif path not in DOCS_ONLY_PATHS:
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
    """Append atomically to a trusted single-writer GitHub runner output.

    Changed-path bytes are untrusted, but ``path`` must be the runner-owned output
    file for this classifier step. Defending against a malicious same-user process
    is outside this function's threat model because that process could write the
    GitHub output directly.
    """
    path = Path(os.path.abspath(path))
    lines = [f"{name}={'true' if value else 'false'}" for name, value in values.items()]
    payload = ("\n".join(lines) + "\n").encode("utf-8")

    _validate_parent_chain(path)
    existing, existing_mode = _read_existing_output(path)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        temporary_stream = os.fdopen(descriptor, "wb", buffering=0)
        descriptor = -1
        with temporary_stream:
            _write_all(temporary_stream, existing + payload)
            temporary_stream.flush()
            os.fsync(temporary_stream.fileno())
        if existing_mode is not None:
            os.chmod(temporary_path, existing_mode)
        os.replace(temporary_path, path)
    finally:
        try:
            if descriptor >= 0:
                os.close(descriptor)
        finally:
            # The random temp belongs to this trusted single-writer invocation.
            temporary_path.unlink(missing_ok=True)


def _validate_parent_chain(path: Path) -> None:
    for parent in reversed((path.parent, *path.parent.parents)):
        try:
            info = parent.lstat()
        except FileNotFoundError as error:
            raise OSError(f"GitHub output parent does not exist: {parent}") from error
        _require_safe_kind(info, parent, directory=True)


def _read_existing_output(path: Path) -> tuple[bytes, int | None]:
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return b"", None
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
        return existing, stat.S_IMODE(final.st_mode)
    finally:
        os.close(descriptor)


def _require_safe_kind(info: os.stat_result, path: Path, *, directory: bool) -> None:
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    file_attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or file_attributes & reparse_attribute:
        raise OSError(f"GitHub output path must not be a link or reparse point: {path}")
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_kind(info.st_mode):
        kind = "directory" if directory else "regular file"
        raise OSError(f"GitHub output path must be a {kind}: {path}")


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
