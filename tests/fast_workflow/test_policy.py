import re

from .support import (
    PROJECT_ROOT,
    markdown_section,
    read,
)


def test_agent_instructions_define_the_micro_task_fast_lane():
    instructions = read("AGENTS.md")
    fast_lane = markdown_section(instructions, "### Micro task fast lane")

    assert "## Task Risk Tiers" in instructions
    assert "### Micro task fast lane" in instructions
    assert "at most three production files" in instructions
    assert "scripts\\verify-fast.ps1" in instructions
    assert "docs/micro-task-template.md" in instructions
    assert (
        "at least one relevant `-BackendTest`, `-FrontendTest`, `-LintFile`, or "
        "`-StaticFile` target" in " ".join(fast_lane.split())
    )
    for token in [
        "comma-separated values",
        "unstaged, staged, and untracked changes",
        "independently committable changeset",
        "target files overlap existing changes",
        "verification shares mutable state",
    ]:
        assert token in " ".join(fast_lane.split())


def test_fast_lane_maps_file_types_to_specific_verification_targets():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split())
        for token in [
            "Python production",
            "`-BackendTest`",
            "Black",
            "changed Python",
            "JavaScript or TypeScript production",
            "`-LintFile`",
            "every changed code file",
            "`-FrontendTest`",
            "behavior",
            "`-StaticFile`",
            "manual check",
            "`-StaticFile` supports only Markdown, plain text, CSS, SCSS, and Less",
            "HTML, JSON, YAML, and YML require complete verification",
            "shared build",
            "deployment",
            "authentication",
            "security",
            "complete verification",
            "ESLint glob or extglob characters",
            "8 MiB",
        ]:
            assert token.casefold() in compact.casefold()


def test_fast_lane_requires_concrete_verification_evidence():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    template = read("docs/micro-task-template.md")

    for document in [fast_lane, template]:
        compact = " ".join(document.split())
        assert "actual command" in compact
        assert "specific targets" in compact
        assert "manual results" in compact
        assert "“verified”" in compact


def test_fast_lane_mapping_applies_regardless_of_mixed_targets():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split()).casefold()
        for token in [
            "every changed static file",
            "regardless of other targets",
            "every changed frontend",
            "unsupported changed files",
            "complete verification",
        ]:
            assert token.casefold() in compact


def test_task_file_policy_scopes_only_non_overlapping_dirty_changes():
    fast_lane = markdown_section(read("AGENTS.md"), "### Micro task fast lane")
    v2_design = read(
        "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    )

    for document in [fast_lane, v2_design]:
        compact = " ".join(document.split()).casefold()
        for token in [
            "`-TaskFile`",
            "clean or isolated checkout",
            "omit",
            "all changed files",
            "unrelated non-overlapping dirty changes",
            "list every task file",
            "actual command",
            "not a verification target",
            "target files overlap existing changes",
            "verification shares mutable state",
            "worktree",
        ]:
            assert token.casefold() in compact

    assert "-TaskFile AGENTS.md,docs/micro-task-template.md" in fast_lane
    assert "-StaticFile AGENTS.md,docs/micro-task-template.md" in fast_lane


def test_micro_task_template_keeps_the_record_concise():
    template = read("docs/micro-task-template.md")

    for field in ["Change", "Acceptance", "Verification"]:
        assert f"**{field}:**" in template

    assert "independent design spec" in template
    assert "implementation plan" in template
    assert "Optional when this is a bug: **Root cause:**" in template
    assert "Optional when scope could easily expand: **Out of scope:**" in template


def test_workflow_source_exempts_qualified_micro_tasks_from_full_steps():
    instructions = read("AGENTS.md")
    compact_instructions = " ".join(instructions.split())

    assert (
        "## Stable Commit Workflow (normal, high-risk, release, and escalated work)"
        in instructions
    )
    assert (
        "Qualified micro tasks use `scripts\\verify-fast.ps1` instead of steps 2 and 3."
        in compact_instructions
    )
    assert (
        "For normal, high-risk, release, or escalated work, run the full commit "
        "verification before committing." in compact_instructions
    )
    assert "verify-before-commit.ps1 -Format" in instructions


def test_workflow_source_delegates_claude_task_rules_to_agents():
    claude = read("CLAUDE.md")

    assert (
        "Task classification, worktree choice, and verification rules are defined only in "
        "`AGENTS.md`." in claude.splitlines()[:8]
    )


def test_fast_lane_boundaries_mark_v2_as_the_current_policy():
    design = read("docs/superpowers/specs/2026-07-28-micro-task-fast-lane-design.md")

    assert "> **Status:** Superseded on conflict details by V2." in design
    assert "[V2 design](2026-07-29-micro-task-fast-lane-v2-design.md)" in design
    assert "[`AGENTS.md`](../../../AGENTS.md)" in design
    assert (
        PROJECT_ROOT
        / "docs/superpowers/specs/2026-07-29-micro-task-fast-lane-v2-design.md"
    ).is_file()


def test_v2_plan_labels_the_historical_dirty_worktree_verification_context():
    plan = read("docs/superpowers/plans/2026-07-29-micro-task-fast-lane-v2.md")
    task_five = markdown_section(
        plan, "### Task 5: Verify the first batch and prepare integration"
    )

    assert "Historical execution context" in task_five
    assert "dirty worktree" in task_five
    assert "not a clean-checkout reproduction command" in task_five


def test_fast_verifier_only_runs_explicit_targets():
    script = read("scripts/verify-fast.ps1")

    for parameter in [
        "FrontendTest",
        "LintFile",
        "BackendTest",
        "StaticFile",
        "TaskFile",
    ]:
        assert f"[string[]]${parameter}" in script

    assert 'Invoke-Step "git diff --check"' in script
    assert "node_modules/.bin/vitest" in script
    assert "node_modules/.bin/eslint" in script
    assert "& $vitest run @($frontendTestTargetsVerified.ToArray())" in script
    assert "& $eslint -- @($lintTargetsVerified.ToArray())" in script
    assert "python -m pytest -q -- @($backendTargetsVerified.ToArray())" in script
    assert "Provide at least one targeted check" in script
    assert "npm test" not in script
    assert "npx eslint" not in script
    assert "npm run build" not in script
    assert 'Invoke-Step "frontend tests"' not in script
    assert 'Invoke-Step "backend tests"' not in script

    extension_list = re.search(r"\$allowedStaticExtensions\s*=\s*@\(([^)]*)\)", script)
    assert extension_list is not None
    assert set(re.findall(r'"(\.[a-z]+)"', extension_list.group(1))) == {
        ".md",
        ".txt",
        ".css",
        ".scss",
        ".less",
    }


def test_untracked_scan_uses_streaming_file_apis():
    script = read("scripts/verify-fast.ps1")

    assert "[System.IO.File]::ReadAllBytes" not in script
    assert "System.IO.FileStream" in script
    assert "System.IO.StreamReader" in script
    assert "StandardOutput.BaseStream" in script
    assert "ls-files -z --others --exclude-standard" in script


def test_fast_verifier_uses_runtime_os_detection_and_ordinal_path_deduplication():
    script = read("scripts/verify-fast.ps1")

    assert "$env:OS" not in script
    assert "RuntimeInformation]::IsOSPlatform" in script
    assert "OSPlatform]::Windows" in script
    assert "$pathComparer = [System.StringComparer]::Ordinal" in script


def test_fast_verifier_rejects_the_complete_eslint_glob_character_set():
    script = read("scripts/verify-fast.ps1")

    assert '[char[]]"*?[]{}()!+@"' in script


def test_fast_lane_preserves_full_verification_boundaries():
    instructions = read("AGENTS.md")
    high_risk = markdown_section(instructions, "### High-risk task")
    boundaries = markdown_section(instructions, "### Full verification boundaries")

    for token in [
        "authentication",
        "security",
        "dependencies",
        "deployment",
        "complete verification",
    ]:
        assert token in high_risk
    for token in [
        "normal",
        "high-risk",
        "release",
        "authentication",
        "security",
        "dependency",
        "deployment",
        "complete verification",
    ]:
        assert token.casefold() in boundaries.casefold()
