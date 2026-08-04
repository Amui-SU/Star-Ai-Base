"""Contract tests for fail-closed CI path classification."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = PROJECT_ROOT / "scripts" / "classify-ci-paths.py"


def _load_classifier() -> ModuleType:
    assert CLASSIFIER_PATH.is_file(), "scripts/classify-ci-paths.py is missing"
    spec = importlib.util.spec_from_file_location("classify_ci_paths", CLASSIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (
            ["docs/user-guide.md"],
            {"backend": False, "frontend": False, "docs_only": True},
        ),
        (["app/main.py"], {"backend": True, "frontend": False, "docs_only": False}),
        (
            ["tests/test_auth.py"],
            {"backend": True, "frontend": False, "docs_only": False},
        ),
        (
            ["frontend/components/App.tsx"],
            {"backend": False, "frontend": True, "docs_only": False},
        ),
        (
            ["frontend/package-lock.json"],
            {"backend": False, "frontend": True, "docs_only": False},
        ),
        (["AGENTS.md"], {"backend": True, "frontend": True, "docs_only": False}),
        (
            ["scripts/verify-fast.ps1"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        (
            [".github/workflows/ci.yml"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        (
            ["unknown.binary"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        (
            ["app/main.py", "frontend/lib/api.ts"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        ([], {"backend": True, "frontend": True, "docs_only": False}),
        (
            ["docs/superpowers/specs/2026-07-29-micro-task-fast-lane-design.md"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        (
            ["docs/superpowers/plans/2026-07-29-micro-task-fast-lane.md"],
            {"backend": True, "frontend": True, "docs_only": False},
        ),
        (
            [r"frontend\components\WindowsPath.tsx"],
            {"backend": False, "frontend": True, "docs_only": False},
        ),
    ],
)
def test_classify_paths(paths: list[str], expected: dict[str, bool]) -> None:
    assert _load_classifier().classify_paths(paths) == expected


def test_force_full_ignores_paths() -> None:
    assert _load_classifier().classify_paths(["docs/readme.md"], force_full=True) == {
        "backend": True,
        "frontend": True,
        "docs_only": False,
    }


def _run_classifier(
    payload: bytes, output: Path, *extra_args: str
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/classify-ci-paths.py",
            "--stdin-zero",
            "--github-output",
            str(output),
            *extra_args,
        ],
        input=payload,
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )


def test_cli_reads_nul_names_and_writes_github_outputs(tmp_path: Path) -> None:
    output = tmp_path / "github-output"

    result = _run_classifier(
        "docs/space name.md\0frontend/lib/中.ts\0".encode(), output
    )

    assert result.returncode == 0, result.stderr.decode()
    assert output.read_text(encoding="utf-8").splitlines() == [
        "backend=false",
        "frontend=true",
        "docs_only=false",
    ]


@pytest.mark.parametrize(
    ("payload", "preexisting_output"),
    [
        (b"docs/ok.md\0\xff\0", False),
        (b"docs/ok.md\0\xff\0", True),
        (b"docs/missing-terminator.md", False),
        (b"docs/missing-terminator.md", True),
    ],
    ids=[
        "invalid-utf8-new-output",
        "invalid-utf8-existing-output",
        "missing-terminal-nul-new-output",
        "missing-terminal-nul-existing-output",
    ],
)
def test_invalid_nul_input_fails_without_touching_output(
    tmp_path: Path, payload: bytes, preexisting_output: bool
) -> None:
    output = tmp_path / "github-output"
    if preexisting_output:
        output.write_bytes(b"existing=true\n")

    result = _run_classifier(payload, output)

    assert result.returncode != 0
    assert b"Invalid changed-path input" in result.stderr
    if preexisting_output:
        assert output.read_bytes() == b"existing=true\n"
    else:
        assert not output.exists()


def test_cli_empty_input_fails_closed_to_both_jobs(tmp_path: Path) -> None:
    output = tmp_path / "github-output"

    result = _run_classifier(b"", output)

    assert result.returncode == 0, result.stderr.decode()
    assert output.read_text(encoding="utf-8").splitlines() == [
        "backend=true",
        "frontend=true",
        "docs_only=false",
    ]


def test_cli_force_full_ignores_docs_only_input(tmp_path: Path) -> None:
    output = tmp_path / "github-output"

    result = _run_classifier(b"docs/readme.md\0", output, "--force-full")

    assert result.returncode == 0, result.stderr.decode()
    assert output.read_text(encoding="utf-8").splitlines() == [
        "backend=true",
        "frontend=true",
        "docs_only=false",
    ]
