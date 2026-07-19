#!/usr/bin/env python3
"""Validate restore archive metadata and print its uncompressed file size."""

from __future__ import annotations

import pathlib
import sys
import tarfile


def inspect_archive(path: str, max_members: int, max_bytes: int) -> int:
    seen: set[str] = set()
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("empty archive")
        total_bytes = sum(member.size for member in members if member.isfile())
        if len(members) > max_members or total_bytes > max_bytes:
            raise ValueError(
                "archive resource limit exceeded: "
                f"members={len(members)}/{max_members}, "
                f"bytes={total_bytes}/{max_bytes}"
            )
        for member in members:
            raw_name = member.name
            path_value = pathlib.PurePosixPath(raw_name)
            parts = tuple(part for part in path_value.parts if part not in ("", "."))
            if (
                path_value.is_absolute()
                or ".." in parts
                or "\\" in raw_name
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"unsafe member: {raw_name!r}")
            if not parts:
                if member.isdir():
                    continue
                raise ValueError("archive root must be a directory")
            normalized = "/".join(parts)
            if normalized in seen:
                raise ValueError(f"duplicate member: {normalized!r}")
            seen.add(normalized)
    return total_bytes


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: inspect-restore-archive.py ARCHIVE MAX_MEMBERS MAX_BYTES",
            file=sys.stderr,
        )
        return 2
    try:
        total = inspect_archive(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
    except (OSError, tarfile.TarError, ValueError) as error:
        print(f"unsafe archive: {error}", file=sys.stderr)
        return 1
    print(total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
