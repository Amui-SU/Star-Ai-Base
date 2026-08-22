import os
import shutil
from pathlib import Path

import pytest

from .support import (
    VerifierRepo,
    run_checked,
    run_verifier,
)

STATIC_FILE_LIMIT_BYTES = 8 * 1024 * 1024


def test_unstaged_whitespace_in_tracked_static_file_fails(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_text("baseline\ninvalid \n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    assert result.returncode != 0


def test_staged_whitespace_in_tracked_static_file_fails(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_text("baseline\ninvalid \n", encoding="utf-8")
    run_checked(["git", "add", "README.md"], repo, environment)

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    assert result.returncode != 0


def test_untracked_whitespace_in_static_file_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("invalid \n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "trailing whitespace" in result.stdout + result.stderr


def test_untracked_terminal_blank_line_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md" in result.stdout + result.stderr
    assert "blank line" in result.stdout + result.stderr


def test_untracked_file_containing_only_one_newline_is_a_terminal_blank_line(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"\n")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "terminal blank line" in result.stdout + result.stderr


def test_untracked_conflict_marker_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("<<<<<<< HEAD\ncontent\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


@pytest.mark.parametrize(
    "marker",
    [
        "<<<<<<<<< branch",
        "<<<<<<<\tbranch",
        "========",
        ">>>>>>>> branch",
        "||||||| base",
    ],
)
def test_untracked_extended_conflict_marker_fails(
    verifier_repo: VerifierRepo, marker: str
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text(f"{marker}\ncontent\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


def test_untracked_conflict_marker_requires_the_whole_line(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("prefix <<<<<<< HEAD suffix\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode == 0, result.stdout + result.stderr


def test_untracked_utf8_bom_conflict_marker_fails(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"\xef\xbb\xbf<<<<<<< HEAD\ncontent\n")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "note.md:1" in result.stdout + result.stderr
    assert "conflict marker" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("encoding", "bom"),
    [
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ],
)
def test_static_file_rejects_utf16_bom_without_nul(
    verifier_repo: VerifierRepo, encoding: str, bom: bytes
):
    repo, environment = verifier_repo
    payload = bom + "\u1234\u5678".encode(encoding)
    assert b"\x00" not in payload
    (repo / "note.md").write_bytes(payload)

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    assert result.returncode != 0
    assert "UTF-8" in result.stdout + result.stderr


def test_untracked_binary_file_with_nul_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"binary\x00invalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode != 0
    assert "NUL" in result.stdout + result.stderr


def test_untracked_invalid_utf8_file_is_skipped(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "binary.txt").write_bytes(b"\xffinvalid \n")

    result = run_verifier(repo, environment, "-StaticFile", "binary.txt")

    assert result.returncode != 0
    assert "UTF-8" in result.stdout + result.stderr


def test_large_untracked_text_file_reports_late_whitespace(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    large_content = ("valid line\n" * 300_000) + "invalid \n"
    (repo / "large.txt").write_text(large_content, encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "large.txt")

    assert result.returncode != 0
    assert "large.txt:300001" in result.stdout + result.stderr
    assert "trailing whitespace" in result.stdout + result.stderr


def test_static_file_rejects_a_single_line_over_the_size_limit(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "large.md").write_bytes(b"x" * (STATIC_FILE_LIMIT_BYTES + 1))

    result = run_verifier(repo, environment, "-StaticFile", "large.md")

    assert result.returncode != 0
    assert (
        "large.md exceeds the 8 MiB static file limit" in result.stdout + result.stderr
    )


def test_large_unsupported_file_is_skipped_before_text_decoding(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("changed", encoding="utf-8")
    (repo / "archive.bin").write_bytes((b"x" * (STATIC_FILE_LIMIT_BYTES + 1)) + b"\xff")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Fast verification does not support changed file: archive.bin" in output
    assert "Skipping non-UTF-8 untracked file: archive.bin" not in output
    assert "static file limit" not in output


def test_untracked_special_character_path_is_enumerated_without_git_quoting(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    relative_path = Path("中文 空格 'quoted'") / "nested" / "note.md"
    target = repo / relative_path
    target.parent.mkdir(parents=True)
    target.write_text("invalid \n", encoding="utf-8")
    windows_powershell = shutil.which("powershell") if os.name == "nt" else None

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        str(relative_path),
        executable=windows_powershell,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert ":1 trailing whitespace" in output
    assert "Could not read untracked file" not in output


def test_untracked_symbolic_link_is_rejected_without_scanning_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    outside = repo.parent / "outside-note.md"
    outside.write_text("invalid \n", encoding="utf-8")
    link = repo / "linked-note.md"
    try:
        link.symlink_to(outside)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "linked-note.md" in output
    assert "symbolic link or reparse point" in output
    assert "trailing whitespace" not in output


def test_static_file_rejects_parent_traversal_to_case_variant_sibling(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    case_probe = repo.parent / "case-sensitivity-probe"
    case_probe.write_text("probe\n", encoding="utf-8")
    if (repo.parent / "CASE-SENSITIVITY-PROBE").exists():
        pytest.skip("case-insensitive filesystem")

    outside = repo.parent / "REPO"
    outside.mkdir()
    (outside / "outside.md").write_text("outside\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "../REPO/outside.md")

    assert result.returncode != 0
    assert "Static file target must not contain '..'" in result.stdout + result.stderr


def test_static_file_rejects_symbolic_link_to_outside_repo(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    outside = repo.parent / "outside"
    outside.mkdir()
    (outside / "outside.md").write_text("outside\n", encoding="utf-8")
    link = repo / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise

    result = run_verifier(repo, environment, "-StaticFile", "linked/outside.md")

    assert result.returncode != 0
    assert "symbolic link" in (result.stdout + result.stderr).casefold()
