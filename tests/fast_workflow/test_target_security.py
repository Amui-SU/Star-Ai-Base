import os
from pathlib import Path

import pytest

from .support import (
    VerifierRepo,
    run_checked,
    run_subprocess_with_timeout,
    run_verifier,
    write_frontend_stub,
)


@pytest.mark.parametrize(
    ("option", "executable", "safe_target", "injected_target"),
    [
        ("-BackendTest", None, "tests/test_probe.py", "--collect-only"),
        ("-FrontendTest", "vitest", "src/probe.test.ts", "--passWithNoTests"),
        ("-LintFile", "eslint", "src/probe.ts", "--fix"),
    ],
)
def test_tool_targets_reject_comma_expanded_option_injection(
    verifier_repo: VerifierRepo,
    tmp_path: Path,
    option: str,
    executable: str | None,
    safe_target: str,
    injected_target: str,
):
    repo, environment = verifier_repo
    target = repo / ("frontend" if option != "-BackendTest" else "") / safe_target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (
            "def test_probe():\n    assert True\n"
            if target.suffix == ".py"
            else "export {};\n"
        ),
        encoding="utf-8",
    )
    if executable is not None:
        write_frontend_stub(repo, executable)
        environment["FAST_VERIFIER_LOG"] = str(tmp_path / "tool-arguments.txt")
        environment["FAST_VERIFIER_EXIT"] = "0"

    result = run_verifier(repo, environment, option, f"{safe_target},{injected_target}")

    assert result.returncode != 0
    assert "must not start with '-'" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("option", "target"),
    [
        ("-BackendTest", "../outside.py"),
        ("-BackendTest", "does-not-exist.py"),
        ("-FrontendTest", "../outside.test.ts"),
        ("-LintFile", "does-not-exist.ts"),
    ],
)
def test_tool_targets_require_existing_non_traversing_relative_files(
    verifier_repo: VerifierRepo, option: str, target: str
):
    repo, environment = verifier_repo
    result = run_verifier(repo, environment, option, target)

    assert result.returncode != 0
    assert "target" in (result.stdout + result.stderr).casefold()


@pytest.mark.parametrize("glob_character", ["*", "?", "[", "]", "{", "}", "!"])
def test_lint_targets_reject_eslint_glob_characters(
    verifier_repo: VerifierRepo, glob_character: str
):
    repo, environment = verifier_repo

    result = run_verifier(
        repo,
        environment,
        "-LintFile",
        f"src/probe{glob_character}target.ts",
    )

    assert result.returncode != 0
    assert "ESLint glob" in result.stdout + result.stderr


def test_backend_target_allows_a_node_id_after_a_verified_python_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo, environment, "-BackendTest", "tests/test_probe.py::test_probe"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_task_file_rejects_a_code_symbolic_link_before_verification(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    linked = repo / "linked.py"
    try:
        linked.symlink_to(outside)
    except OSError as error:
        if os.name == "nt":
            pytest.skip(f"cannot create symbolic links: {error}")
        raise
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "linked.py",
        "-BackendTest",
        "tests/test_probe.py",
    )

    assert result.returncode != 0
    assert "symbolic link" in (result.stdout + result.stderr).casefold()


@pytest.mark.parametrize(
    ("option", "repo_relative_path", "verifier_target"),
    [
        pytest.param("-BackendTest", "linked.py", "linked.py", id="backend"),
        pytest.param(
            "-FrontendTest",
            "frontend/src/linked.test.ts",
            "src/linked.test.ts",
            id="frontend",
        ),
        pytest.param("-LintFile", "frontend/src/linked.ts", "src/linked.ts", id="lint"),
        pytest.param("-TaskFile", "linked.py", "linked.py", id="code-task-file"),
    ],
)
def test_code_targets_reject_git_index_mode_120000(
    verifier_repo: VerifierRepo,
    option: str,
    repo_relative_path: str,
    verifier_target: str,
):
    repo, environment = verifier_repo
    target = repo / repo_relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("outside-target", encoding="utf-8")
    blob = run_subprocess_with_timeout(
        ["git", "hash-object", "-w", repo_relative_path],
        cwd=repo,
        environment=environment,
        timeout_seconds=20,
    )
    assert blob.returncode == 0, blob.stdout + blob.stderr
    run_checked(
        [
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{blob.stdout.strip()},{repo_relative_path}",
        ],
        repo,
        environment,
    )

    arguments = [option, verifier_target]
    if option == "-TaskFile":
        backend_test = repo / "tests" / "test_probe.py"
        backend_test.parent.mkdir()
        backend_test.write_text(
            "def test_probe():\n    assert True\n", encoding="utf-8"
        )
        arguments.extend(["-BackendTest", "tests/test_probe.py"])

    result = run_verifier(repo, environment, *arguments)

    assert result.returncode != 0
    assert "Git symbolic link" in result.stdout + result.stderr


def test_changed_python_is_black_checked_before_backend_tests(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "change.py").write_text("value=1\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(repo, environment, "-BackendTest", "tests/test_probe.py")

    assert result.returncode != 0
    assert "changed Python formatting" in result.stdout
    assert "targeted backend tests" not in result.stdout


def test_black_checks_all_scoped_python_files(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "one.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "two.py").write_text("other = 2\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "one.py,two.py",
        "-BackendTest",
        "tests/test_probe.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 files would be left unchanged" in result.stdout + result.stderr


@pytest.mark.parametrize("git_state", ["unstaged", "staged"])
def test_task_file_diff_check_treats_brackets_as_literal_pathspecs(
    verifier_repo: VerifierRepo, git_state: str
):
    repo, environment = verifier_repo
    path = repo / "[ab].md"
    path.write_text("invalid \n", encoding="utf-8")
    run_checked(["git", "add", "-N", "[ab].md"], repo, environment)
    if git_state == "staged":
        run_checked(["git", "add", "[ab].md"], repo, environment)

    result = run_verifier(
        repo,
        environment,
        "-TaskFile",
        "[ab].md",
        "-StaticFile",
        "[ab].md",
    )

    assert result.returncode != 0
    assert "trailing whitespace" in result.stdout + result.stderr


def test_static_file_checks_each_case_distinct_changed_file_on_case_sensitive_filesystem(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "Foo.md").write_text("one\n", encoding="utf-8")
    if (repo / "foo.md").exists():
        pytest.skip("case-insensitive filesystem")
    (repo / "foo.md").write_text("two\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "Foo.md")

    assert result.returncode != 0
    assert "foo.md" in result.stdout + result.stderr
