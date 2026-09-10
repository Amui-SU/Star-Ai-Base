import pytest

from .support import (
    VerifierRepo,
    run_checked,
    run_verifier,
)


def test_comma_separated_backend_targets_run_each_file(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_one.py").write_text(
        "def test_one():\n    assert True\n", encoding="utf-8"
    )
    (tests / "test_two.py").write_text(
        "def test_two():\n    assert True\n", encoding="utf-8"
    )

    result = run_verifier(
        repo,
        environment,
        "-BackendTest",
        "tests/test_one.py,tests/test_two.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout
    assert "targeted frontend tests" not in result.stdout


@pytest.mark.parametrize("static_file", ["docs/note.md", "styles/fix.css"])
def test_static_file_accepts_supported_extensions(
    verifier_repo: VerifierRepo, static_file: str
):
    repo, environment = verifier_repo
    target = repo / static_file
    target.parent.mkdir(parents=True)
    target.write_text("content\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", static_file)

    assert result.returncode == 0, result.stdout + result.stderr


def test_static_file_rejects_unsupported_extensions(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo
    (repo / "unsafe.py").write_text("print('unsafe')\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "unsafe.py")

    assert result.returncode != 0
    assert "Unsupported static file" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("static_file", "content"),
    [
        ("package.json", b"{}\n"),
        ("compose.yml", b"services: {}\n"),
        (".github/workflows/ci.yaml", b"name: ci\n"),
        ("page.html", b"<p>content</p>\n"),
    ],
)
def test_static_file_rejects_structured_and_config_files(
    verifier_repo: VerifierRepo, static_file: str, content: bytes
):
    repo, environment = verifier_repo
    target = repo / static_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    result = run_verifier(repo, environment, "-StaticFile", static_file)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert f"Unsupported static file: {static_file}" in output
    assert "use full verification" in output


@pytest.mark.parametrize(
    ("git_state", "code_path"),
    [("untracked", "change.py"), ("unstaged", "frontend/widget.tsx")],
)
def test_static_file_requires_changed_target_when_only_code_changed(
    verifier_repo: VerifierRepo, git_state: str, code_path: str
):
    repo, environment = verifier_repo
    target = repo / code_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if git_state == "unstaged":
        target.write_bytes(b"export const value = 1;\n")
        run_checked(["git", "add", code_path], repo, environment)
        run_checked(
            [
                "git",
                "commit",
                "--no-gpg-sign",
                "--no-verify",
                "-m",
                "track code target",
            ],
            repo,
            environment,
        )
    target.write_bytes(b"changed\n")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Static file target is not changed: README.md" in output


def test_static_file_requires_its_target_to_be_changed(verifier_repo: VerifierRepo):
    repo, environment = verifier_repo

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Static file target is not changed: README.md" in output


def test_static_only_verification_rejects_code_hidden_by_changed_readme(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "README.md").write_bytes(b"changed\n")
    (repo / "change.py").write_text("changed\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "README.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert (
        "Changed Python files require at least one -BackendTest target: change.py"
        in output
    )


def test_static_only_verification_requires_every_changed_static_file(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n", encoding="utf-8")
    (repo / "style.css").write_text("body {}\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing -StaticFile target for changed file: style.css" in output


def test_static_only_verification_accepts_all_changed_static_files(
    verifier_repo: VerifierRepo,
):
    repo, environment = verifier_repo
    (repo / "note.md").write_text("content\n", encoding="utf-8")
    (repo / "style.css").write_text("body {}\n", encoding="utf-8")

    result = run_verifier(repo, environment, "-StaticFile", "note.md,style.css")

    assert result.returncode == 0, result.stdout + result.stderr
