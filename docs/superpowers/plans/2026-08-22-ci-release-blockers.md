# CI Release Blockers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** partial

**Goal:** Make the release branch pass its Linux backend workflow and mandatory production dependency audit without weakening either guard.

**Architecture:** A focused contract prevents repository PowerShell scripts from shadowing the read-only `$IsWindows` automatic variable, while a mechanical rename preserves existing behavior. A separate npm 10 lockfile remediation updates only vulnerable transitive resolutions, followed by one integrated release verification and remote CI gate.

**Tech Stack:** PowerShell Core, Python 3.12, pytest, Node 22.13.1, npm 10.9.2, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-22-ci-release-blockers-design.md`

## Global Constraints

- Do not lower, skip, conditionally bypass, or add an exception to `npm audit --omit=dev --audit-level=high`.
- Do not use `npm audit fix --force` merely to make CI green.
- Use Node `22.13.1` and npm `10.9.2` for lockfile generation and dependency acceptance.
- Preserve all existing PowerShell path, suffix, junction, target, and staging behavior; only rename the repository-owned platform flag.
- Keep pull request 7 as a draft and do not merge it into `main`.
- Treat any failed, cancelled, or skipped required CI job as an unsuccessful release check.

---

### Task 1: Prevent PowerShell Automatic-Variable Shadowing

**Files:**

- Modify: `scripts/verify-fast.ps1`
- Modify: `scripts/verify-staged.ps1`
- Modify: `scripts/worktree-deps.ps1`
- Test: `tests/fast_workflow/test_cli_targets.py`
- Test: `tests/developer_workflow/test_verify_staged.py`
- Modify: `tests/developer_workflow/test_worktree_deps.py`

**Interfaces:**

- Consumes: repository PowerShell scripts executed by fast, staged, and worktree workflow tests.
- Produces: the internal `$runningOnWindows` Boolean flag in each affected script; no public CLI change.

- [x] **Step 1: Run the existing PowerShell Core workflows and verify RED**

Add a focused worktree dependency test that invokes `worktree-deps.ps1`
explicitly with `pwsh`, without changing the Windows-only shim compiler used by
the rest of that module.

Run:

```powershell
python -m pytest -q `
  tests/fast_workflow/test_cli_targets.py::test_static_file_accepts_supported_extensions `
  tests/developer_workflow/test_verify_staged.py::test_empty_index_succeeds_without_starting_formatters `
  tests/developer_workflow/test_worktree_deps.py::test_status_handles_space_and_unicode_worktree_path
```

Expected: all three workflows fail under `pwsh` with `Cannot overwrite variable
IsWindows because it is read-only or constant`.

- [x] **Step 2: Apply the minimal mechanical rename**

In each affected script, change the declaration and every read of
`$isWindows` to `$runningOnWindows`. Do not change the expressions that compute
the Boolean or either branch selected from it.

- [x] **Step 3: Verify the focused workflows and regressions**

Run:

```powershell
python -m pytest -q `
  tests/developer_workflow/test_verify_staged.py `
  tests/developer_workflow/test_worktree_deps.py `
  tests/fast_workflow
```

Expected: all tests pass, and no subprocess reports `Cannot overwrite variable
IsWindows because it is read-only or constant`.

- [x] **Step 4: Commit the portability fix**

Stage only the test helper, plan, and three PowerShell scripts; verify the
staged list, then commit:

```powershell
git commit -m "fix: avoid PowerShell automatic variable collision"
```

### Task 2: Remediate Production Dependency Audit Findings

**Files:**

- Modify: `frontend/package-lock.json`
- Test: `tests/developer_workflow/test_frontend_dependency_contract.py`

**Interfaces:**

- Consumes: `frontend/package.json`, `.nvmrc`, npm registry advisory data, and the npm 10 lockfile format.
- Produces: a reproducible lockfile whose production tree contains `brace-expansion >=5.0.9` and `nanoid >=3.3.18` where those packages are resolved.

- [x] **Step 1: Detach shared dependencies and record the failing audit**

If `scripts/worktree-deps.ps1 -Mode Status` reports `shared`, run `-Mode Detach`
before any npm mutation. Then use the pinned npm version:

```powershell
npx --yes npm@10.9.2 --version
npx --yes npm@10.9.2 ci --no-audit --no-fund
npx --yes npm@10.9.2 audit --omit=dev --audit-level=high
```

Expected: npm reports version `10.9.2`; the audit exits nonzero and names the
existing production findings before the lockfile changes.

- [x] **Step 2: Apply the non-forced lockfile remediation**

Run:

```powershell
npx --yes npm@10.9.2 audit fix --package-lock-only
```

Do not add `--force`. Inspect the diff and stop if npm changes
`frontend/package.json`, introduces a direct dependency, or performs a broad
unrelated major upgrade.

- [x] **Step 3: Verify a clean reproducible install and audit GREEN**

Run:

```powershell
npx --yes npm@10.9.2 ci --no-audit --no-fund
npx --yes npm@10.9.2 ls --depth=0 --json
npx --yes npm@10.9.2 audit --omit=dev --audit-level=high
```

Expected: all commands exit 0; `npm ls` contains no `problems`; the production
audit reports no high or critical vulnerabilities.

- [x] **Step 4: Verify dependency contracts and the frontend**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py
$env:VITEST_MAX_THREADS='4'
$env:VITEST_MIN_THREADS='1'
npm test
npm run lint
npm run build
```

Expected: dependency contracts, frontend tests, lint, and production build all
pass with the new lockfile.

- [x] **Step 5: Commit the lockfile remediation**

Stage only `frontend/package-lock.json`, confirm `frontend/package.json` is
unchanged, then commit:

```powershell
git commit -m "fix: remediate frontend production advisories"
```

### Task 3: Close The Resolved Dependency Exception

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `docs/security/dependency-audit-exceptions.md`
- Modify: `tests/test_ci_workflow.py`
- Modify: `tests/test_dependency_security_policy.py`

**Interfaces:**

- Consumes: the patched development dependency tree and the expired temporary exception.
- Produces: a blocking full high-severity audit and a dated closed-exception record.

- [x] **Step 1: Write and run the failing security lifecycle contracts**

Require the full audit step to omit `continue-on-error`, require the current
register to contain no active exception, and retain generic deadline and
removal-criteria checks for any future active exception.

- [x] **Step 2: Close the exception and strengthen CI**

Remove `continue-on-error` from the full dependency audit. Mark
`GHSA-mh99-v99m-4gvg` closed on 2026-08-22 and record patched
`brace-expansion` versions `1.1.18` and `5.0.9`.

- [x] **Step 3: Verify the security policy and full audit**

```powershell
python -m pytest -q tests/test_ci_workflow.py tests/test_dependency_security_policy.py
npx --yes npm@10.9.2 audit --audit-level=high
```

Expected: all policy tests pass and the full high-severity audit exits 0.

- [x] **Step 4: Commit the security policy closure**

```powershell
git commit -m "ci: close resolved dependency audit exception"
```

### Task 4: Verify And Integrate The Release Fixes

**Files:**

- Modify: `docs/superpowers/plans/2026-08-22-ci-release-blockers.md`
- Modify: `docs/superpowers/plans/README.md`

**Interfaces:**

- Consumes: Task 1 and Task 2 commits plus the repository verification scripts.
- Produces: a verified fast-forward update on `release/video-security-integration-20260729` and a closed implementation plan.

- [ ] **Step 1: Run focused acceptance checks**

Run the Task 1 regression command, then:

```powershell
python scripts/generate-plan-index.py --check
npx --yes npm@10.9.2 audit --omit=dev --audit-level=high
```

Expected: every command exits 0.

- [ ] **Step 2: Run complete commit verification**

Run from the isolated worktree:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1
```

Expected: Black, pytest, Prettier, ESLint, Vitest, the Next.js production build,
and Git whitespace checks all pass. If the format run changes a file, inspect
and include only changes already in this plan's scope.

- [ ] **Step 3: Close and commit the implementation plan**

After local verification, mark completed implementation steps, add a completion
record with exact test counts and commands, change the plan status only when no
local work remains, then run:

```powershell
python scripts/generate-plan-index.py
python scripts/generate-plan-index.py --check
python -m pytest -q tests/developer_workflow/test_plan_lifecycle.py
```

Commit the plan and generated index with:

```powershell
git commit -m "docs: close CI release blocker fixes"
```

- [ ] **Step 4: Fast-forward merge and recheck the release branch**

From the main repository, verify the release checkout is clean, then:

```powershell
git merge --ff-only chore/ci-release-blockers
python -m pytest -q `
  tests/fast_workflow/test_cli_targets.py::test_static_file_accepts_supported_extensions `
  tests/developer_workflow/test_verify_staged.py::test_empty_index_succeeds_without_starting_formatters `
  tests/developer_workflow/test_worktree_deps.py::test_status_runs_under_powershell_core `
  tests/developer_workflow/test_frontend_dependency_contract.py `
  tests/developer_workflow/test_plan_lifecycle.py
python scripts/generate-plan-index.py --check
```

Expected: merge and all checks succeed before worktree cleanup.

- [ ] **Step 5: Clean up, push, and monitor both CI runs**

Detach shared dependencies if present, remove the owned worktree, prune, delete
the merged feature branch, and push without force:

```powershell
git push origin release/video-security-integration-20260729
```

Use GitHub CLI to identify both the `push` and `pull_request` CI runs for the
new full commit SHA. Wait for both to complete and confirm `Changes`, `Backend`,
`Frontend`, and `CI Success` are successful in each run. Leave pull request 7
as a draft and do not merge it.
