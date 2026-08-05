"""Contract tests for fail-closed CI path classification."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = PROJECT_ROOT / "AGENTS.md"
CLASSIFIER_PATH = PROJECT_ROOT / "scripts" / "classify-ci-paths.py"
CI_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
OUTPUT_VALUES = {"backend": True, "frontend": False, "docs_only": False}
OUTPUT_PAYLOAD = b"backend=true\nfrontend=false\ndocs_only=false\n"
PATH_AWARE_CI_RULES = {
    "Pull requests": "pr-routing=job-level-only",
    "Unknown and policy paths": "unknown-policy-paths=backend+frontend",
    "Protected pushes": "protected-pushes[main,release/**]=full-backend+frontend",
    "Required check": "required-check=CI Success",
}


class _GitHubActionsSafeLoader(yaml.SafeLoader):
    pass


_GitHubActionsSafeLoader.yaml_implicit_resolvers = {
    key: list(resolvers)
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for first_character in ("o", "O"):
    _GitHubActionsSafeLoader.yaml_implicit_resolvers[first_character] = [
        (tag, resolver)
        for tag, resolver in _GitHubActionsSafeLoader.yaml_implicit_resolvers.get(
            first_character, []
        )
        if tag != "tag:yaml.org,2002:bool"
    ]


def _load_classifier() -> ModuleType:
    assert CLASSIFIER_PATH.is_file(), "scripts/classify-ci-paths.py is missing"
    spec = importlib.util.spec_from_file_location("classify_ci_paths", CLASSIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_markdown_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _fence_opener(line: str) -> tuple[str, int] | None:
    match = re.fullmatch(r" {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)", line)
    if match is None:
        return None
    marker = match.group("marker")
    if marker[0] == "`" and "`" in match.group("info"):
        return None
    return marker[0], len(marker)


def _is_fence_closer(line: str, marker: str, length: int) -> bool:
    return (
        re.fullmatch(rf" {{0,3}}{re.escape(marker)}{{{length},}}[ \t]*", line)
        is not None
    )


def _lines_outside_fences(value: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    offset = 0
    for raw_line in value.splitlines(keepends=True):
        line = raw_line.removesuffix("\n")
        if fence is not None:
            if _is_fence_closer(line, *fence):
                fence = None
        else:
            fence = _fence_opener(line)
            if fence is None:
                lines.append((offset, line))
        offset += len(raw_line)
    return lines


def _without_fenced_code(value: str) -> str:
    return "\n".join(line for _, line in _lines_outside_fences(value))


def _atx_heading(line: str) -> tuple[int, str] | None:
    match = re.fullmatch(r" {0,3}(?P<marks>#{1,6})(?:[ \t]+(?P<title>.*))?", line)
    if match is None:
        return None
    title = (match.group("title") or "").strip()
    title = re.sub(r"[ \t]+#+[ \t]*$", "", title).strip()
    return len(match.group("marks")), title


def _extract_path_aware_ci_section(policy: str) -> str:
    policy = _normalize_markdown_newlines(policy)
    headings = [
        (offset, heading)
        for offset, line in _lines_outside_fences(policy)
        if (heading := _atx_heading(line)) is not None
    ]
    targets = [item for item in headings if item[1] == (3, "Path-aware CI")]
    assert len(targets) == 1, "AGENTS.md must define exactly one Path-aware CI section"
    start = targets[0][0]
    end = next(
        (offset for offset, (level, _) in headings if offset > start and level <= 3),
        len(policy),
    )
    return policy[start:end]


def _parse_path_aware_ci_rules(section: str) -> dict[str, str]:
    lines = _without_fenced_code(section).splitlines()
    assert lines and _atx_heading(lines[0]) == (3, "Path-aware CI")
    content = [line for line in lines[1:] if line.strip()]
    assert content and content[0].strip() == "Inline policy tokens are normative."
    rules: dict[str, str] = {}
    current_label: str | None = None
    for line in content[1:]:
        bullet = re.fullmatch(r"- \*\*(?P<label>[^*]+):\*\*[ \t]*(?P<body>.*)", line)
        if bullet:
            label = bullet.group("label")
            assert label in PATH_AWARE_CI_RULES, f"Unknown Path-aware CI label: {label}"
            assert label not in rules, f"Duplicate Path-aware CI label: {label}"
            rules[label] = bullet.group("body").strip()
            current_label = label
            continue
        assert (
            current_label is not None and line[:1].isspace()
        ), f"Unexpected Path-aware CI section content: {line}"
        rules[current_label] = f"{rules[current_label]} {line.strip()}".strip()
    assert set(rules) == set(PATH_AWARE_CI_RULES), "Missing Path-aware CI rule"
    assert all(rules.values()), "Path-aware CI rule bodies must not be empty"
    return rules


def _assert_path_aware_ci_rules(section: str, rules: dict[str, str]) -> None:
    for label, expected_token in PATH_AWARE_CI_RULES.items():
        assert rules[label] == f"`{expected_token}`"
    tokens = re.findall(r"`([^`\r\n]+=[^`\r\n]+)`", _without_fenced_code(section))
    assert sorted(tokens) == sorted(PATH_AWARE_CI_RULES.values())


def _assert_path_aware_ci_policy(policy: str) -> None:
    policy = _normalize_markdown_newlines(policy)
    section = _extract_path_aware_ci_section(policy)
    _assert_path_aware_ci_rules(section, _parse_path_aware_ci_rules(section))
    outside = _without_fenced_code(policy.replace(section, "", 1))
    assert all(token not in outside for token in PATH_AWARE_CI_RULES.values())


VALID_PATH_AWARE_CI_SECTION = """### Path-aware CI

Inline policy tokens are normative.

- **Pull requests:** `pr-routing=job-level-only`
- **Unknown and policy paths:** `unknown-policy-paths=backend+frontend`
- **Protected pushes:** `protected-pushes[main,release/**]=full-backend+frontend`
- **Required check:** `required-check=CI Success`
"""
VALID_PATH_AWARE_CI_POLICY = (
    "# Instructions\n\n" + VALID_PATH_AWARE_CI_SECTION + "\n## Next section\n"
)
SWAPPED_PATH_AWARE_CI_LABELS_POLICY = (
    VALID_PATH_AWARE_CI_POLICY.replace("**Pull requests:**", "**Temporary:**")
    .replace("**Protected pushes:**", "**Pull requests:**")
    .replace("**Temporary:**", "**Protected pushes:**")
)


def test_agents_defines_path_aware_ci_policy_boundaries() -> None:
    _assert_path_aware_ci_policy(AGENTS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "policy",
    [
        VALID_PATH_AWARE_CI_POLICY.replace(
            "- **Required check:** `required-check=CI Success`\n",
            "",
        ),
        VALID_PATH_AWARE_CI_POLICY.replace(
            "unknown-policy-paths=backend+frontend",
            "unknown-policy-paths=backend",
        ),
        SWAPPED_PATH_AWARE_CI_LABELS_POLICY,
        VALID_PATH_AWARE_CI_POLICY.replace(
            "`pr-routing=job-level-only`",
            "`pr-routing=job-level-only` `pr-routing=job-level-only`",
        ),
        VALID_PATH_AWARE_CI_POLICY.replace(
            "`pr-routing=job-level-only`",
            "`pr-routing=job-level-only` `extra-policy=true`",
        ),
        VALID_PATH_AWARE_CI_POLICY + "Outside: `required-check=CI Success`\n",
        VALID_PATH_AWARE_CI_POLICY.replace(
            "protected-pushes[main,release/**]=full-backend+frontend",
            "protected-pushes[release/**]=full-backend+frontend",
        ),
        VALID_PATH_AWARE_CI_POLICY.replace(
            "protected-pushes[main,release/**]=full-backend+frontend",
            "protected-pushes[main]=full-backend+frontend",
        ),
        VALID_PATH_AWARE_CI_POLICY.replace(
            "protected-pushes[main,release/**]=full-backend+frontend",
            "protected-pushes[main,release/*]=full-backend+frontend",
        ),
        VALID_PATH_AWARE_CI_POLICY.replace(
            "protected-pushes[main,release/**]=full-backend+frontend",
            "protected-pushes[develop,hotfix/**]=full-backend+frontend",
        ),
    ],
    ids=(
        "missing-token",
        "changed-token-value",
        "swapped-labels",
        "duplicate-token",
        "extra-token",
        "token-outside-section",
        "protected-push-missing-main",
        "protected-push-missing-release",
        "protected-push-changed-release-glob",
        "protected-push-other-branches",
    ),
)
def test_path_aware_ci_policy_rejects_token_mutations(policy: str) -> None:
    with pytest.raises(AssertionError):
        _assert_path_aware_ci_policy(policy)


@pytest.mark.parametrize(
    "section",
    [
        VALID_PATH_AWARE_CI_SECTION
        + "- **Pull requests:** `pr-routing=job-level-only`\n",
        VALID_PATH_AWARE_CI_SECTION.replace("Pull requests", "PR routing", 1),
        VALID_PATH_AWARE_CI_SECTION.replace(
            "- **Required check:** `required-check=CI Success`\n",
            "",
        ),
    ],
    ids=("duplicate-label", "unknown-label", "missing-label"),
)
def test_path_aware_ci_policy_rejects_invalid_bullet_structure(section: str) -> None:
    with pytest.raises(AssertionError):
        _parse_path_aware_ci_rules(section)


@pytest.mark.parametrize(
    "policy",
    [
        VALID_PATH_AWARE_CI_POLICY,
        VALID_PATH_AWARE_CI_POLICY.replace(
            "- **Protected pushes:** `protected-pushes[main,release/**]=full-backend+frontend`",
            "- **Protected pushes:**\n  `protected-pushes[main,release/**]=full-backend+frontend`",
        ),
    ],
    ids=("inline-token", "wrapped-token"),
)
def test_path_aware_ci_policy_accepts_token_formatting(policy: str) -> None:
    _assert_path_aware_ci_policy(policy)


def test_path_aware_ci_policy_accepts_atx_closing_hashes() -> None:
    policy = VALID_PATH_AWARE_CI_POLICY.replace(
        "### Path-aware CI",
        "### Path-aware CI ###",
        1,
    )

    _assert_path_aware_ci_policy(policy)


def test_backtick_fence_with_backtick_in_info_does_not_hide_policy_content() -> None:
    invalid_fence = "```markdown`bad\n### Path-aware CI\n`extra-policy=true`\n````\n\n"

    with pytest.raises(AssertionError):
        _assert_path_aware_ci_policy(invalid_fence + VALID_PATH_AWARE_CI_POLICY)


@pytest.mark.parametrize(
    ("opener", "closer"),
    [("```markdown", "````"), ("   ~~~~ markdown`allowed", "   ~~~~~")],
    ids=("backtick-fence", "tilde-fence"),
)
def test_path_aware_ci_heading_inside_outer_fence_is_ignored(
    opener: str,
    closer: str,
) -> None:
    fenced_example = f"{opener}\n### Path-aware CI\n{closer}\n\n"

    _assert_path_aware_ci_policy(fenced_example + VALID_PATH_AWARE_CI_POLICY)


@pytest.mark.parametrize(
    ("opener", "closer"),
    [("```text", "````"), ("   ~~~~ text", "   ~~~~~")],
    ids=("backtick-fence", "tilde-fence"),
)
def test_fenced_heading_and_token_inside_path_aware_section_are_ignored(
    opener: str,
    closer: str,
) -> None:
    fenced_example = f"{opener}\n## Example\n`extra-policy=true`\n{closer}\n"
    policy = VALID_PATH_AWARE_CI_POLICY.replace(
        "## Next section\n",
        fenced_example + "## Next section\n",
    )

    _assert_path_aware_ci_policy(policy)


@pytest.mark.parametrize("newline", ["\r\n", "\r"], ids=("crlf", "cr"))
def test_path_aware_ci_policy_normalizes_input_newlines(newline: str) -> None:
    policy = VALID_PATH_AWARE_CI_POLICY.replace("\n", newline)

    _assert_path_aware_ci_policy(policy)


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


@pytest.mark.parametrize(
    "invalid_path",
    [
        "",
        "/docs/readme.md",
        "../docs/readme.md",
        "C:/docs/readme.md",
        "docs/../../README.md",
        "docs//readme.md",
        "./docs/readme.md",
        r"\\server\share\docs\readme.md",
    ],
)
def test_invalid_repository_relative_path_fails_closed(invalid_path: str) -> None:
    assert _load_classifier().classify_paths([invalid_path]) == {
        "backend": True,
        "frontend": True,
        "docs_only": False,
    }


def test_one_invalid_path_forces_mixed_input_to_full_ci() -> None:
    assert _load_classifier().classify_paths(
        ["docs/valid.md", "frontend/component.ts", "../docs/readme.md"]
    ) == {
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


def test_trusted_single_writer_appends_to_existing_bytes_in_stable_order(
    tmp_path: Path,
) -> None:
    classifier = _load_classifier()
    output = tmp_path / "github-output"
    existing = b"previous=exact\r\n"
    output.write_bytes(existing)

    classifier.write_outputs(output, OUTPUT_VALUES)

    assert output.read_bytes() == existing + OUTPUT_PAYLOAD


def test_output_writer_declares_trusted_single_writer_precondition() -> None:
    docstring = _load_classifier().write_outputs.__doc__

    assert docstring is not None
    assert "trusted single-writer" in docstring


def test_write_outputs_preserves_existing_file_mode(tmp_path: Path) -> None:
    classifier = _load_classifier()
    output = tmp_path / "github-output"
    output.write_bytes(b"previous=exact\n")
    expected_mode = stat.S_IMODE(output.stat().st_mode)

    classifier.write_outputs(output, OUTPUT_VALUES)

    assert stat.S_IMODE(output.stat().st_mode) == expected_mode


def _symlink_or_skip(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        pytest.skip(f"filesystem does not permit symbolic links: {error}")


def test_write_outputs_rejects_target_symlink_without_touching_link_target(
    tmp_path: Path,
) -> None:
    classifier = _load_classifier()
    outside = tmp_path / "outside-output"
    existing = b"outside=exact\n"
    outside.write_bytes(existing)
    output = tmp_path / "github-output"
    _symlink_or_skip(output, outside)

    with pytest.raises(OSError, match="link|reparse"):
        classifier.write_outputs(output, OUTPUT_VALUES)

    assert output.is_symlink()
    assert outside.read_bytes() == existing
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_write_outputs_rejects_parent_symlink_without_touching_link_target(
    tmp_path: Path,
) -> None:
    classifier = _load_classifier()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    existing = b"outside=exact\n"
    (real_parent / "github-output").write_bytes(existing)
    linked_parent = tmp_path / "linked-parent"
    _symlink_or_skip(linked_parent, real_parent, directory=True)
    output = linked_parent / "github-output"

    with pytest.raises(OSError, match="link|reparse"):
        classifier.write_outputs(output, OUTPUT_VALUES)

    assert linked_parent.is_symlink()
    assert (real_parent / "github-output").read_bytes() == existing
    assert list(real_parent.glob(f".{output.name}.*.tmp")) == []


def test_write_outputs_rejects_non_regular_target_without_artifacts(
    tmp_path: Path,
) -> None:
    classifier = _load_classifier()
    output = tmp_path / "github-output"
    output.mkdir()

    with pytest.raises(OSError):
        classifier.write_outputs(output, OUTPUT_VALUES)

    assert output.is_dir()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_write_outputs_rejects_non_directory_parent_without_artifacts(
    tmp_path: Path,
) -> None:
    classifier = _load_classifier()
    parent = tmp_path / "not-a-directory"
    existing = b"parent=exact\n"
    parent.write_bytes(existing)
    output = parent / "github-output"

    with pytest.raises(OSError):
        classifier.write_outputs(output, OUTPUT_VALUES)

    assert parent.read_bytes() == existing
    assert not output.exists()


class _MidWriteFailure:
    def __init__(self, stream) -> None:
        self._stream = stream

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._stream.__exit__(exc_type, exc_value, traceback)

    def write(self, payload: bytes) -> int:
        partial_length = max(1, len(payload) // 2)
        self._stream.write(payload[:partial_length])
        self._stream.flush()
        raise OSError("injected mid-write failure")

    def flush(self) -> None:
        self._stream.flush()

    def fileno(self) -> int:
        return self._stream.fileno()


@pytest.mark.parametrize("failure_at", ["write", "replace"])
@pytest.mark.parametrize("preexisting_output", [False, True])
def test_trusted_single_writer_failure_preserves_destination_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_at: str,
    preexisting_output: bool,
) -> None:
    classifier = _load_classifier()
    output = tmp_path / "github-output"
    existing = b"previous=exact\r\n"
    if preexisting_output:
        output.write_bytes(existing)

    if failure_at == "write":
        real_fdopen = os.fdopen

        def fail_during_write(*args, **kwargs):
            return _MidWriteFailure(real_fdopen(*args, **kwargs))

        monkeypatch.setattr(os, "fdopen", fail_during_write)
    else:

        def fail_during_replace(*_args, **_kwargs) -> None:
            raise OSError("injected replace failure")

        monkeypatch.setattr(os, "replace", fail_during_replace)

    with pytest.raises(OSError, match=failure_at):
        classifier.write_outputs(output, OUTPUT_VALUES)

    if preexisting_output:
        assert output.read_bytes() == existing
    else:
        assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def _load_ci_workflow() -> dict[str, object]:
    value = yaml.load(
        CI_PATH.read_text(encoding="utf-8"), Loader=_GitHubActionsSafeLoader
    )
    assert isinstance(value, dict)
    return value


def _job(workflow: dict[str, object], name: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[name]
    assert isinstance(job, dict)
    return job


def _steps(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _bash_executable() -> str | None:
    if os.name != "nt":
        return shutil.which("bash")
    git_exec_path = subprocess.run(
        ["git", "--exec-path"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    git_bash = Path(git_exec_path).parents[2] / "bin" / "bash.exe"
    return str(git_bash) if git_bash.is_file() else None


def test_ci_has_changes_and_summary_jobs() -> None:
    workflow_text = CI_PATH.read_text(encoding="utf-8")

    assert "\n  changes:\n" in workflow_text
    assert "\n  backend:\n" in workflow_text
    assert "\n  frontend:\n" in workflow_text
    assert "\n  ci-success:\n" in workflow_text


def test_workflow_contract_loader_does_not_use_node_or_node_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_run = subprocess.run
    real_read_text = Path.read_text

    def reject_node(command, *args, **kwargs):
        if command and Path(command[0]).stem.lower() == "node":
            raise AssertionError("pytest workflow contracts must not require Node")
        return real_run(command, *args, **kwargs)

    def reject_node_modules(path: Path, *args, **kwargs):
        if "node_modules" in path.parts:
            raise AssertionError("pytest workflow contracts must not read node_modules")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", reject_node)
    monkeypatch.setattr(Path, "read_text", reject_node_modules)

    assert "jobs" in _load_ci_workflow()


def test_workflow_yaml_preserves_on_and_protected_push_triggers() -> None:
    workflow = _load_ci_workflow()

    assert "on" in workflow
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert "pull_request" in triggers
    push = triggers["push"]
    assert isinstance(push, dict)
    assert push["branches"] == ["main", "release/**"]


def test_changes_job_exposes_classifier_outputs_and_uses_full_history() -> None:
    changes = _job(_load_ci_workflow(), "changes")

    assert changes["outputs"] == {
        "backend": "${{ steps.classify.outputs.backend }}",
        "frontend": "${{ steps.classify.outputs.frontend }}",
        "docs_only": "${{ steps.classify.outputs.docs_only }}",
    }
    steps = _steps(changes)
    checkout = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout["with"] == {"fetch-depth": 0}
    setup_python = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    )
    assert setup_python["with"] == {"python-version": "3.12"}
    classifier = next(step for step in steps if step.get("id") == "classify")
    assert classifier["shell"] == "bash"
    assert classifier["env"] == {
        "EVENT_NAME": "${{ github.event_name }}",
        "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha || github.sha }}",
    }
    script = str(classifier["run"])
    assert '[[ "$EVENT_NAME" == "push" ]]' in script
    assert "--force-full" in script
    assert 'git diff --name-only -z --no-renames "$BASE_SHA" "$HEAD_SHA"' in script
    assert script.count("scripts/classify-ci-paths.py") == 2
    assert script.count('--github-output "$GITHUB_OUTPUT"') == 2


def test_heavy_jobs_are_gated_by_changes_outputs() -> None:
    workflow = _load_ci_workflow()
    backend = _job(workflow, "backend")
    frontend = _job(workflow, "frontend")

    assert backend["needs"] == "changes"
    assert backend["if"] == "needs.changes.outputs.backend == 'true'"
    assert frontend["needs"] == "changes"
    assert frontend["if"] == "needs.changes.outputs.frontend == 'true'"


def test_backend_uses_official_pip_cache() -> None:
    setup_python = next(
        step
        for step in _steps(_job(_load_ci_workflow(), "backend"))
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    )

    assert setup_python["with"] == {
        "python-version": "3.12",
        "cache": "pip",
        "cache-dependency-path": "requirements.txt",
    }


def test_frontend_verification_steps_are_preserved() -> None:
    names = {step.get("name") for step in _steps(_job(_load_ci_workflow(), "frontend"))}

    assert {
        "Install frontend dependencies",
        "Audit production dependencies",
        "Report full dependency audit",
        "Install Playwright Chromium",
        "Run lint",
        "Run frontend tests",
        "Build frontend",
        "Run browser tests",
    } <= names


def test_all_actions_remain_pinned_to_commit_shas() -> None:
    workflow = _load_ci_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    uses = [
        str(step["uses"])
        for job in jobs.values()
        if isinstance(job, dict)
        for step in _steps(job)
        if "uses" in step
    ]

    assert uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", value) for value in uses)


@pytest.mark.parametrize(
    (
        "changes_result",
        "backend_expected",
        "backend_result",
        "frontend_expected",
        "frontend_result",
        "docs_only",
        "expected_code",
    ),
    [
        ("success", "true", "success", "false", "skipped", "false", 0),
        ("success", "false", "skipped", "true", "success", "false", 0),
        ("success", "false", "skipped", "false", "skipped", "true", 0),
        ("success", "false", "skipped", "false", "skipped", "false", 1),
        ("success", "", "skipped", "false", "skipped", "true", 1),
        ("success", "garbage", "skipped", "false", "skipped", "true", 1),
        ("success", "false", "skipped", "", "skipped", "true", 1),
        ("success", "false", "skipped", "garbage", "skipped", "true", 1),
        ("success", "false", "skipped", "false", "skipped", "", 1),
        ("success", "false", "skipped", "false", "skipped", "garbage", 1),
        ("success", "false", "success", "false", "skipped", "false", 1),
        ("success", "true", "skipped", "false", "skipped", "false", 1),
        ("success", "true", "failure", "false", "skipped", "false", 1),
        ("success", "false", "skipped", "false", "success", "false", 1),
        ("success", "false", "skipped", "true", "skipped", "false", 1),
        ("success", "false", "skipped", "true", "failure", "false", 1),
        ("success", "true", "success", "false", "skipped", "true", 1),
        ("failure", "false", "skipped", "false", "skipped", "true", 1),
    ],
)
def test_ci_summary_enforces_expected_job_results(
    changes_result: str,
    backend_expected: str,
    backend_result: str,
    frontend_expected: str,
    frontend_result: str,
    docs_only: str,
    expected_code: int,
) -> None:
    bash = _bash_executable()
    if bash is None:
        pytest.skip("bash is required to execute the CI summary contract")
    summary = _job(_load_ci_workflow(), "ci-success")
    assert summary["if"] == "always()"
    assert summary["needs"] == ["changes", "backend", "frontend"]
    require_step = next(
        step for step in _steps(summary) if step.get("name") == "Require expected jobs"
    )
    assert require_step["shell"] == "bash"
    assert require_step["env"] == {
        "CHANGES_RESULT": "${{ needs.changes.result }}",
        "BACKEND_EXPECTED": "${{ needs.changes.outputs.backend }}",
        "BACKEND_RESULT": "${{ needs.backend.result }}",
        "FRONTEND_EXPECTED": "${{ needs.changes.outputs.frontend }}",
        "FRONTEND_RESULT": "${{ needs.frontend.result }}",
        "DOCS_ONLY": "${{ needs.changes.outputs.docs_only }}",
    }
    env = os.environ.copy()
    env.update(
        {
            "CHANGES_RESULT": changes_result,
            "BACKEND_EXPECTED": backend_expected,
            "BACKEND_RESULT": backend_result,
            "FRONTEND_EXPECTED": frontend_expected,
            "FRONTEND_RESULT": frontend_result,
            "DOCS_ONLY": docs_only,
        }
    )

    result = subprocess.run(
        [bash, "-c", str(require_step["run"])],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_code, result.stderr


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
    ).stdout


def test_pull_request_rename_keeps_the_deleted_source_boundary(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "rename-fixture"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "CI Contract")
    _git(repo, "config", "user.email", "ci@example.invalid")
    source = repo / "app" / "moved.py"
    source.parent.mkdir()
    source.write_text("unchanged = True\n", encoding="utf-8")
    _git(repo, "add", "--", "app/moved.py")
    _git(repo, "commit", "--quiet", "-m", "add backend source")
    base_sha = _git(repo, "rev-parse", "HEAD").decode().strip()
    (repo / "docs").mkdir()
    _git(repo, "mv", "--", "app/moved.py", "docs/moved.md")
    _git(repo, "commit", "--quiet", "-m", "move source to docs")
    head_sha = _git(repo, "rev-parse", "HEAD").decode().strip()

    rename_aware = _git(repo, "diff", "--name-only", "-z", base_sha, head_sha)
    no_renames = _git(
        repo,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        base_sha,
        head_sha,
    )
    rename_output = tmp_path / "rename-output"
    no_rename_output = tmp_path / "no-rename-output"

    assert _run_classifier(rename_aware, rename_output).returncode == 0
    assert rename_output.read_text(encoding="utf-8").splitlines() == [
        "backend=false",
        "frontend=false",
        "docs_only=true",
    ]
    assert _run_classifier(no_renames, no_rename_output).returncode == 0
    assert no_rename_output.read_text(encoding="utf-8").splitlines() == [
        "backend=true",
        "frontend=false",
        "docs_only=false",
    ]
