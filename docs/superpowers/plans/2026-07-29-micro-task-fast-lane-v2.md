# Micro-task Fast Lane V2 Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

The checklist below records the completed development sequence. The current
contract tests live in `tests/fast_workflow`,
with a lightweight split guard in `tests/test_fast_workflow_structure.py`; current
policy and verifier behavior supersede illustrative snippets in this plan.

**Goal:** Make micro-task verification reliable and genuinely lightweight without weakening normal, high-risk, or release verification.

**Architecture:** Keep workflow policy in `AGENTS.md` and command orchestration in `scripts/verify-fast.ps1`. Add process-level pytest coverage around the public PowerShell CLI, normalize comma-separated targets for `-File`, validate all Git change states, and provide a restricted static-file path for documentation and stylesheet-only changes.

**Tech Stack:** PowerShell, Git, Python 3.12, pytest, Vitest, ESLint, Markdown

---

### Task 1: Add a real PowerShell contract-test harness

**Files:**

- Modify: `tests/fast_workflow`

- [x] **Step 1: Add the subprocess and temporary-repository helpers**

Add imports for `os`, `shutil`, `subprocess`, `textwrap`, and `pytest`. Add helpers that:

```python
def powershell_executable() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required for verify-fast contract tests")
    return executable


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def init_fast_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "scripts/verify-fast.ps1", root / "scripts/verify-fast.ps1")
    run(["git", "init"], root)
    run(["git", "config", "user.email", "tests@example.com"], root)
    run(["git", "config", "user.name", "Tests"], root)
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    run(["git", "add", "README.md"], root)
    run(["git", "commit", "-m", "baseline"], root)
    return root


def invoke_fast(root: Path, *arguments: str):
    executable = powershell_executable()
    shell_args = ["-NoProfile"]
    if Path(executable).stem.lower() == "powershell":
        shell_args.extend(["-ExecutionPolicy", "Bypass"])
    return run(
        [executable, *shell_args, "-File", str(root / "scripts/verify-fast.ps1"), *arguments],
        root,
    )
```

- [x] **Step 2: Add failing public-CLI tests**

Add tests proving that comma-separated backend targets remain two arguments, static Markdown/CSS files are accepted, code passed through `-StaticFile` is rejected, and a stray positional target fails without starting frontend verification. Use two tiny pytest files in the temporary repository for the backend case.

```python
def test_fast_verifier_accepts_comma_separated_backend_targets(tmp_path):
    root = init_fast_repo(tmp_path)
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_one.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")
    (tests / "test_two.py").write_text("def test_two():\n    assert True\n", encoding="utf-8")

    result = invoke_fast(
        root,
        "-BackendTest",
        "tests/test_one.py,tests/test_two.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout
    assert "targeted frontend tests" not in result.stdout


@pytest.mark.parametrize("relative_path", ["docs/note.md", "styles/fix.css"])
def test_fast_verifier_accepts_static_files(tmp_path, relative_path):
    root = init_fast_repo(tmp_path)
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("safe content\n", encoding="utf-8")

    result = invoke_fast(root, "-StaticFile", relative_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_fast_verifier_rejects_code_as_static_file(tmp_path):
    root = init_fast_repo(tmp_path)
    (root / "unsafe.py").write_text("print('unsafe')\n", encoding="utf-8")

    result = invoke_fast(root, "-StaticFile", "unsafe.py")

    assert result.returncode != 0
    assert "Unsupported static file" in result.stdout + result.stderr
```

- [x] **Step 3: Run the focused tests and confirm RED**

Run:

```powershell
python -m pytest -q tests/fast_workflow -k "comma_separated or static_file"
```

Expected: failures because the current script treats the comma-separated paths as one pytest target and does not define `-StaticFile`.

- [x] **Step 4: Commit only the failing contract tests**

```powershell
git add -- tests/fast_workflow
git commit -m "test: expose fast verifier cli gaps"
```

### Task 2: Implement target normalization and static-file verification

**Files:**

- Modify: `scripts/verify-fast.ps1`
- Test: `tests/fast_workflow`

- [x] **Step 1: Disable positional binding and normalize targets**

Add `[CmdletBinding(PositionalBinding = $false)]`, the `StaticFile` parameter, and a helper that trims array values, splits comma-separated input, removes empty items, and returns a string array:

```powershell
[CmdletBinding(PositionalBinding = $false)]
param(
    [string[]]$FrontendTest = @(),
    [string[]]$LintFile = @(),
    [string[]]$BackendTest = @(),
    [string[]]$StaticFile = @()
)

function Expand-Targets {
    param([string[]]$Values)

    return @(
        $Values |
            ForEach-Object { $_ -split "," } |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
}
```

Normalize all four parameters immediately after helper declarations and reject an empty target set before the first Git command.

- [x] **Step 2: Validate restricted static targets**

Resolve each target beneath the repository root, reject paths that escape the root or do not exist, and allow only `.md`, `.txt`, `.css`, `.scss`, and `.less`. HTML, JSON, YAML, and YML require complete verification. Emit `Unsupported static file: <path>` for a disallowed extension.

- [x] **Step 3: Run the Task 1 tests and confirm GREEN**

Run:

```powershell
python -m pytest -q tests/fast_workflow -k "comma_separated or static_file"
```

Expected: all selected tests pass.

- [x] **Step 4: Add failing tests for local frontend executables**

Extend the structural contract to require `.bin/vitest` and `.bin/eslint` resolution and to forbid `npm test`, `npx eslint`, `npm run build`, and unscoped test commands. The test should fail against the current npm/npx implementation before it is changed.

- [x] **Step 5: Call installed frontend executables directly**

Resolve `vitest.cmd`/`eslint.cmd` on Windows and `vitest`/`eslint` elsewhere under `frontend/node_modules/.bin`. If a requested command is missing, print a focused dependency error and return nonzero. Invoke Vitest with `run` and the normalized test targets, and ESLint with normalized lint targets.

- [x] **Step 6: Run the focused workflow suite**

Run:

```powershell
python -m pytest -q tests/fast_workflow
```

Expected: all workflow tests pass.

- [x] **Step 7: Commit the CLI implementation**

```powershell
git add -- scripts/verify-fast.ps1 tests/fast_workflow
git commit -m "fix: make fast verification targets reliable"
```

### Task 3: Protect unstaged, staged, and untracked content

**Files:**

- Modify: `tests/fast_workflow`
- Modify: `scripts/verify-fast.ps1`

- [x] **Step 1: Add failing Git-state contract tests**

Using `init_fast_repo`, add three tests:

```python
def test_fast_verifier_rejects_unstaged_whitespace(tmp_path):
    root = init_fast_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("bad trailing whitespace   \n", encoding="utf-8")
    result = invoke_fast(root, "-StaticFile", "README.md")
    assert result.returncode != 0


def test_fast_verifier_rejects_staged_whitespace(tmp_path):
    root = init_fast_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("bad staged whitespace   \n", encoding="utf-8")
    run(["git", "add", "README.md"], root)
    result = invoke_fast(root, "-StaticFile", "README.md")
    assert result.returncode != 0


def test_fast_verifier_rejects_untracked_whitespace(tmp_path):
    root = init_fast_repo(tmp_path)
    note = root / "note.md"
    note.write_text("bad new whitespace   \n", encoding="utf-8")
    result = invoke_fast(root, "-StaticFile", "note.md")
    assert result.returncode != 0
```

- [x] **Step 2: Run the three tests and confirm RED**

Run:

```powershell
python -m pytest -q tests/fast_workflow -k "whitespace"
```

Expected: unstaged may already fail, while staged and untracked cases expose the missing checks.

- [x] **Step 3: Add staged and untracked checks**

Run both `git diff --check` and `git diff --cached --check`. Enumerate untracked files with `git ls-files --others --exclude-standard`. For text files, reject trailing spaces/tabs, whitespace-only final lines, and lines equal to unresolved Git conflict markers. Detect binary content by a NUL byte and skip its content scan.

Limit explicit static-file validation to the paths supplied by the caller, while repository whitespace checks cover all task changes in the clean or isolated worktree.

- [x] **Step 4: Run the Git-state tests and full workflow suite**

Run:

```powershell
python -m pytest -q tests/fast_workflow -k "whitespace"
python -m pytest -q tests/fast_workflow
```

Expected: both commands pass.

- [x] **Step 5: Commit the Git-state protection**

```powershell
git add -- scripts/verify-fast.ps1 tests/fast_workflow
git commit -m "fix: verify every fast-lane git state"
```

### Task 4: Remove policy contradictions

**Files:**

- Modify: `tests/fast_workflow`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/micro-task-template.md`
- Modify: `docs/superpowers/specs/2026-07-28-micro-task-fast-lane-design.md`

- [x] **Step 1: Add failing policy assertions**

Require the instructions to state that qualified micro tasks substitute `verify-fast.ps1` for the complete verification steps, that full verification applies to normal/high-risk/release work, that a focused commit is conditional on authorization, and that overlapping changes—not any dirty file—trigger worktree isolation. Require the concise three-field template and a pointer from `CLAUDE.md` to `AGENTS.md` as the workflow source of truth.

- [x] **Step 2: Run policy tests and confirm RED**

Run:

```powershell
python -m pytest -q tests/fast_workflow -k "instructions or template or boundaries"
```

Expected: failures against the contradictory stable-commit and six-field rules.

- [x] **Step 3: Update the workflow source of truth**

In `AGENTS.md`:

- state that micro tasks run `verify-fast.ps1` instead of Stable Commit Workflow steps 2 and 3;
- make the Stable Commit Workflow heading explicitly apply to normal/high-risk/release changes;
- change worktree selection to overlap/shared-state risk;
- replace mandatory commit language with a single independently committable changeset;
- define the conditional three-field record.

Update the original fast-lane design to match the implemented interface and mark it superseded by the V2 design where details differ. Simplify `docs/micro-task-template.md`. Add one short workflow-source pointer near the top of `CLAUDE.md` without duplicating the policy.

- [x] **Step 4: Run policy and complete workflow tests**

Run:

```powershell
python -m pytest -q tests/fast_workflow
```

Expected: all tests pass.

- [x] **Step 5: Commit the policy update**

```powershell
git add -- AGENTS.md CLAUDE.md docs/micro-task-template.md docs/superpowers/specs/2026-07-28-micro-task-fast-lane-design.md tests/fast_workflow
git commit -m "docs: align policy with micro-task fast lane"
```

### Task 5: Verify the first batch and prepare integration

**Files:**

- Verify all first-batch files and commits.

- [x] **Step 1: Run focused verification through the updated public CLI**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-fast.ps1 `
  -BackendTest tests/fast_workflow/test_policy.py `
  -StaticFile AGENTS.md,CLAUDE.md,docs/micro-task-template.md,docs/superpowers/specs/2026-07-28-micro-task-fast-lane-design.md
```

Expected: targeted pytest and all Git/static checks pass without starting frontend tests or a production build.

> **Historical execution context:** This command was run while the listed
> first-batch files were present in a dirty worktree. It records that completed
> run and is not a clean-checkout reproduction command, because `-StaticFile`
> intentionally rejects unchanged targets. Steps 2 and 3 below record the final
> clean-tree regression and repository-state gates.

- [x] **Step 2: Run adjacent process-script regressions**

Run:

```powershell
python -m pytest -q tests/fast_workflow tests/test_dev_script_boundaries.py
```

Expected: all tests pass.

- [x] **Step 3: Inspect scope and history**

Run:

```powershell
git diff --check
git diff --cached --check
git status --short
git log --oneline --decorate -6
```

Expected: no uncommitted files, no whitespace errors, and only the design, tests, implementation, and policy commits are ahead of the starting branch.

- [x] **Step 4: Request code review**

Use `superpowers:requesting-code-review` against the branch diff. Address every confirmed important finding with a failing test first, then rerun Steps 1–3.

- [x] **Step 5: Hand off the verified first batch**

Report the worktree path, commits, verification commands, and remaining second-batch scope. Do not merge, push, or modify the global hook until explicitly requested.
