#!/usr/bin/env python3
"""Classify changed repository paths for path-aware CI routing."""

from __future__ import annotations

import argparse
import sys
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


def classify_paths(paths: list[str], force_full: bool = False) -> dict[str, bool]:
    """Return the required CI jobs, defaulting uncertain inputs to full CI."""
    if force_full:
        return {"backend": True, "frontend": True, "docs_only": False}

    backend = False
    frontend = False
    docs_only = bool(paths)
    for raw_path in paths:
        path = raw_path.replace("\\", "/")
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

    if not paths:
        backend = frontend = True
        docs_only = False
    return {"backend": backend, "frontend": frontend, "docs_only": docs_only}


def read_zero_paths(stream: BinaryIO) -> list[str]:
    """Read strict UTF-8 paths from terminal-NUL-delimited input."""
    payload = stream.read()
    chunks = payload.split(b"\0")
    if chunks[-1] != b"":
        raise ValueError("NUL-delimited input must end with NUL")
    return [chunk.decode("utf-8", errors="strict") for chunk in chunks[:-1]]


def write_outputs(path: Path, values: dict[str, bool]) -> None:
    """Write a complete GitHub output payload after all input is validated."""
    lines = [f"{name}={'true' if value else 'false'}" for name, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
