from pathlib import Path

import pytest

from .support import (
    VerifierRepo,
    run_checked,
    run_verifier,
    write_frontend_stub,
    write_frontend_target,
)


def test_task_file_scope_ignores_unrelated_untracked_configuration(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "settings.toml").write_bytes(b"enabled = true \n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_task_file_must_be_changed(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "unrelated.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Task file is not changed: README.md" in output


def test_task_file_scope_still_requires_lint_for_changed_typescript(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    target = repo / "frontend" / "src" / "widget.ts"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"export const value = 1;\n")
    write_frontend_target(repo, "src/widget.test.ts")
    write_frontend_stub(repo, "vitest")
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "vitest-arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "frontend/src/widget.ts",
        "-FrontendTest",
        "src/widget.test.ts",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -LintFile target for changed frontend file: src/widget.ts" in output


def test_omitting_task_file_keeps_full_changed_worktree_mapping(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "settings.toml").write_bytes(b"enabled = true\n")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "settings.toml" in output
    assert "use full verification" in output


@pytest.mark.parametrize("git_state", ["unstaged", "staged", "untracked"])
def test_task_file_scope_rejects_whitespace_in_each_git_state(
    verifier_repo: VerifierRepo, git_state: str
):
    repo, environment = verifier_repo
    relative_path = "README.md" if git_state != "untracked" else "note.md"
    (repo / relative_path).write_bytes(b"invalid \n")
    if git_state == "staged":
        run_checked(["git", "add", relative_path], repo, environment)

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        relative_path,
        "-StaticFile",
        relative_path,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "trailing whitespace" in output


def test_task_file_scope_supports_untracked_unicode_path(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    relative_path = "中文 空格/说明.md"
    target = repo / relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes("内容\n".encode())
    (repo / "settings.toml").write_bytes(b"enabled = true\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        relative_path,
        "-StaticFile",
        relative_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_task_file_rejects_normalized_duplicates(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "README.md,.\\README.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Duplicate task file: .\\README.md" in output


def test_task_file_must_stay_within_repository(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "../outside.md",
        "-StaticFile",
        "README.md",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Task file must stay within project root: ../outside.md" in output


def test_task_file_does_not_count_as_a_verification_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")

    result = run_verifier(repo, environment, "-TaskFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Provide at least one targeted check" in output


def test_backend_target_cannot_hide_missing_lint_for_changed_frontend_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    frontend_file = repo / "frontend" / "src" / "widget.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_bytes(b"export const value = 2;\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")
    write_frontend_target(repo, "src/widget.tsx")

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        "README.md",
        "-BackendTest",
        "tests/test_probe.py",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Missing -LintFile target for changed frontend file: src/widget.tsx" in output
    )


def test_mixed_targets_continue_when_static_backend_and_lint_mapping_is_complete(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    frontend_file = repo / "frontend" / "src" / "widget.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_bytes(b"export const value = 2;\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")
    write_frontend_target(repo, "src/widget.tsx")
    write_frontend_stub(repo, "eslint")
    log = tmp_path / "eslint-arguments.txt"
    environment["FAST_VERIFIER_LOG"] = str(log)
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(
        repo,
        environment,
        "-StaticFile",
        "README.md",
        "-BackendTest",
        "tests/test_probe.py",
        "-LintFile",
        "src/widget.tsx",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").split() == ["--", "src/widget.tsx"]


def test_changed_python_requires_backend_target_even_with_frontend_target(
    verifier_repo: VerifierRepo, tmp_path: Path
):
    repo, environment = verifier_repo
    (repo / "change.py").write_bytes(b"value = 2\n")
    write_frontend_target(repo, "src/unrelated.test.ts")
    write_frontend_stub(repo, "vitest")
    environment["FAST_VERIFIER_LOG"] = str(tmp_path / "vitest-arguments.txt")
    environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, "-FrontendTest", "src/unrelated.test.ts")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Changed Python files require at least one -BackendTest target: change.py"
        in output
    )


def test_changed_static_file_requires_target_even_with_backend_target(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_bytes(b"content\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -StaticFile target for changed file: note.md" in output


def test_unsupported_changed_extension_requires_full_verification(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "settings.toml").write_bytes(b"enabled = true\n")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_bytes(b"def test_probe():\n    assert True\n")

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Fast verification does not support changed file: settings.toml; "
        "use full verification." in output
    )
