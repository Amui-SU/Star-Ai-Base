# Generated Plan Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned

**Goal:** Generate the implementation-plan index deterministically from each plan's authoritative status field and detect committed index drift.

**Architecture:** A dependency-free Python script owns status parsing, Markdown table rendering, generated-region replacement, and check/write behavior. Focused pytest tests load the script as a module, exercise its pure functions in temporary directories, and verify the committed README is current.

**Tech Stack:** Python 3.12 standard library, pytest, Markdown, PowerShell verification scripts

---

### Task 1: Define Generator Contracts

**Files:**

- Create: `tests/developer_workflow/test_plan_index_generator.py`
- Create: `scripts/generate-plan-index.py`

- [ ] **Step 1: Write failing parser and renderer tests**

Create a test module that loads `scripts/generate-plan-index.py` with
`importlib.util.spec_from_file_location`. Use temporary plan files to assert:

```python
def test_render_index_sorts_plans_and_uses_declared_statuses(tmp_path):
    plans_root = tmp_path / "plans"
    plans_root.mkdir()
    (plans_root / "2026-02-b.md").write_text(
        "# B\n\n**Status:** completed\n", encoding="utf-8"
    )
    (plans_root / "2026-01-a.md").write_text(
        "# A\n\n**Status:** planned\n", encoding="utf-8"
    )

    rendered = generator.render_index(plans_root)

    assert rendered.index("2026-01-a.md") < rendered.index("2026-02-b.md")
    assert "| [2026-01-a.md](2026-01-a.md)" in rendered
    assert "| planned" in rendered
```

Also assert `extract_status()` raises `ValueError` for missing, duplicate, and
unsupported statuses.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_plan_index_generator.py
```

Expected: FAIL because `scripts/generate-plan-index.py` does not exist.

- [ ] **Step 3: Implement status parsing and deterministic table rendering**

Implement these public functions without third-party dependencies:

```python
ALLOWED_STATUSES = {"completed", "partial", "superseded", "planned"}
STATUS_PATTERN = re.compile(r"^\*\*Status:\*\* ([a-z]+)$", re.MULTILINE)


def extract_status(path: Path) -> str:
    statuses = STATUS_PATTERN.findall(path.read_text(encoding="utf-8"))
    if len(statuses) != 1 or statuses[0] not in ALLOWED_STATUSES:
        raise ValueError(
            f"{path.name}: expected exactly one allowed **Status:** field"
        )
    return statuses[0]


def render_index(plans_root: Path) -> str:
    plans = sorted(path for path in plans_root.glob("*.md") if path.name != "README.md")
    rows = [(f"[{path.name}]({path.name})", extract_status(path)) for path in plans]
    plan_width = max([len("Plan"), *(len(plan) for plan, _ in rows)])
    status_width = max([len("Status"), *(len(status) for _, status in rows)])
    lines = [
        f"| {'Plan':<{plan_width}} | {'Status':<{status_width}} |",
        f"| {'-' * plan_width} | {'-' * status_width} |",
    ]
    lines.extend(
        f"| {plan:<{plan_width}} | {status:<{status_width}} |"
        for plan, status in rows
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: all parser and renderer tests pass.

### Task 2: Add Safe README Replacement And Check Mode

**Files:**

- Modify: `tests/developer_workflow/test_plan_index_generator.py`
- Modify: `scripts/generate-plan-index.py`

- [ ] **Step 1: Write failing replacement and drift tests**

Add tests proving the generator replaces only the marked region, rejects
missing or duplicate markers, writes in default mode, and does not write in
check mode:

```python
def test_update_index_check_mode_reports_drift_without_writing(tmp_path):
    plans_root, index_path = create_plan_fixture(tmp_path)
    original = index_path.read_text(encoding="utf-8")

    result = generator.update_index(plans_root, index_path, check=True)

    assert result == 1
    assert index_path.read_text(encoding="utf-8") == original
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run the focused pytest command. Expected: FAIL because marker replacement and
`update_index()` are not implemented.

- [ ] **Step 3: Implement marker validation and CLI modes**

Add exact marker constants and functions:

```python
GENERATED_START = "<!-- BEGIN GENERATED PLAN INDEX -->"
GENERATED_END = "<!-- END GENERATED PLAN INDEX -->"


def replace_generated_region(index_text: str, rendered: str) -> str:
    if index_text.count(GENERATED_START) != 1 or index_text.count(GENERATED_END) != 1:
        raise ValueError("README must contain exactly one generated index marker pair")
    start = index_text.index(GENERATED_START) + len(GENERATED_START)
    end = index_text.index(GENERATED_END)
    if start >= end:
        raise ValueError("generated index markers are out of order")
    return f"{index_text[:start]}\n\n{rendered}\n\n{index_text[end:]}"


def update_index(plans_root: Path, index_path: Path, check: bool) -> int:
    current = index_path.read_text(encoding="utf-8")
    expected = replace_generated_region(current, render_index(plans_root))
    if expected == current:
        return 0
    if check:
        print("Plan index is stale. Run: python scripts/generate-plan-index.py")
        return 1
    index_path.write_text(expected, encoding="utf-8", newline="\n")
    return 0
```

Use `argparse` for the sole public flag `--check`; resolve the project root
from `Path(__file__).resolve().parents[1]`. Catch `ValueError`, print its message
to stderr, and exit nonzero without modifying README.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the focused pytest command. Expected: all generator tests pass.

### Task 3: Migrate And Guard The Committed Index

**Files:**

- Modify: `docs/superpowers/plans/README.md`
- Modify: `tests/developer_workflow/test_plan_lifecycle.py`

- [ ] **Step 1: Write the failing committed-index check**

Load the generator in the lifecycle test and add:

```python
def test_committed_plan_index_matches_generated_output():
    current = INDEX_PATH.read_text(encoding="utf-8")
    expected = generator.replace_generated_region(
        current, generator.render_index(PLANS_ROOT)
    )
    assert current == expected
```

- [ ] **Step 2: Run the lifecycle tests and verify RED**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_plan_index_generator.py tests/developer_workflow/test_plan_lifecycle.py
```

Expected: FAIL because README does not yet contain generated-region markers.

- [ ] **Step 3: Mark the table and generate it**

Update README to state that plan status fields are authoritative, remove the
manual `Notes` column, surround the table with:

```markdown
<!-- BEGIN GENERATED PLAN INDEX -->
<!-- END GENERATED PLAN INDEX -->
```

Then run:

```powershell
python scripts/generate-plan-index.py
python scripts/generate-plan-index.py --check
```

Expected: both commands exit 0; the second command changes no files.

- [ ] **Step 4: Run focused workflow regression tests**

Run the combined pytest command from Step 2. Expected: all tests pass.

### Task 4: Close And Verify The Change

**Files:**

- Modify: `docs/superpowers/plans/2026-08-07-generated-plan-index.md`
- Modify: `docs/superpowers/plans/README.md`

- [ ] **Step 1: Close the implementation plan**

Change this plan's status to `completed`, check every implementation step, add
a completion record containing the exact verification commands, and rerun:

```powershell
python scripts/generate-plan-index.py
```

- [ ] **Step 2: Run repository verification**

Run:

```powershell
git diff --check
python scripts/generate-plan-index.py --check
python -m pytest -q tests/developer_workflow/test_plan_index_generator.py tests/developer_workflow/test_plan_lifecycle.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1 -Format -SkipFrontendTests -SkipFrontendBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1 -SkipFrontendTests -SkipFrontendBuild
```

Expected: all commands exit 0 with no formatting, lifecycle, backend, or
whitespace failures.

- [ ] **Step 3: Commit the implementation**

Stage only the generator, focused tests, README, and this plan. Verify the
staged file list, then commit:

```powershell
git commit -m "docs: generate implementation plan index"
```

- [ ] **Step 4: Merge, recheck, and publish**

Fast-forward merge the feature branch into
`release/video-security-integration-20260729`, rerun the focused pytest and
`--check` commands, remove the owned worktree, delete the merged feature branch,
and push the release branch to `origin`.
