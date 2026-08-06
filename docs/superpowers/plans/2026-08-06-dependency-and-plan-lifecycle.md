# Dependency And Plan Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned

**Goal:** Make clean frontend installs reproducible and give every implementation plan an enforced lifecycle status.

**Architecture:** Record npm's lockfile-resolved optional packages explicitly instead of deleting them after installation, and publish a non-blocking Node/npm baseline shared by local tooling and CI. Add pytest policy guards plus a plan index so status metadata, completed checklists, and supersession links cannot drift.

**Tech Stack:** Node.js, npm, JSON lockfile v3, GitHub Actions YAML, Python 3.12, pytest, Markdown.

---

### Task 1: Lock The Frontend Dependency Contract

**Files:**

- Create: `.nvmrc`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/developer_workflow/test_frontend_dependency_contract.py`

- [ ] **Step 1: Write failing toolchain and optional-dependency tests**

Create tests that load `.nvmrc`, the manifest, lockfile, and CI YAML as text or
structured JSON. Assert Node `22.13.1`, package manager `npm@10.9.2`, CI's use of
`.nvmrc`, and exact optional versions for `@emnapi/runtime`,
`@img/sharp-wasm32`, and `@tybys/wasm-util` in both manifest and lockfile.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py
```

Expected: FAIL because `.nvmrc`, `packageManager`, optional declarations, and
the CI node-version-file contract are absent.

- [ ] **Step 3: Add the canonical toolchain baseline**

Create `.nvmrc` containing `22.13.1`, set
`"packageManager": "npm@10.9.2"` in `frontend/package.json`, and change the CI
setup-node input from `node-version: "22"` to `node-version-file: ".nvmrc"`.

- [ ] **Step 4: Record the optional compatibility dependencies**

Add the following exact `optionalDependencies` and update only the existing
lockfile through npm:

```json
{
  "@emnapi/runtime": "1.11.1",
  "@img/sharp-wasm32": "0.35.3",
  "@tybys/wasm-util": "0.10.2"
}
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py
```

Expected: PASS.

### Task 2: Enforce Plan Lifecycle Metadata

**Files:**

- Create: `tests/developer_workflow/test_plan_lifecycle.py`
- Create: `docs/superpowers/plans/README.md`
- Modify: `docs/superpowers/plans/*.md`

- [ ] **Step 1: Write the failing lifecycle policy test**

Scan every plan except `README.md`. Require one status matching
`completed|partial|superseded|planned`, require every plan in the index exactly
once, reject unchecked steps in completed plans, and require superseded entries
to identify a replacement.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_plan_lifecycle.py
```

Expected: FAIL because historical plans lack standardized status metadata and
the index does not exist.

- [ ] **Step 3: Add the lifecycle index and definitions**

Create `docs/superpowers/plans/README.md` with the four status definitions and
one row per plan. Mark the original `2026-07-28-micro-task-fast-lane.md` as
`superseded` by `2026-07-29-micro-task-fast-lane-v2.md`; mark plans with current
implementation evidence as `completed`.

- [ ] **Step 4: Normalize historical plan headers and checklists**

Add one standard status line near each plan title. Convert remaining unchecked
steps to checked steps only for plans classified `completed`. Replace the V2
plan's non-standard historical status sentence with the standard status line
while retaining its explanatory paragraph.

- [ ] **Step 5: Remove stale dependency limitation text**

Update `2026-07-30-worktree-dependency-reuse.md` so its completion record names
the optional-dependency contract instead of claiming the primary installation
is currently unhealthy.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_plan_lifecycle.py
```

Expected: PASS with all plans indexed and no completed plan containing an
unchecked step.

### Task 3: Prove A Fresh Install Is Healthy

**Files:**

- Verify: `frontend/package.json`
- Verify: `frontend/package-lock.json`

- [ ] **Step 1: Create a disposable install fixture**

Copy only `frontend/package.json` and `frontend/package-lock.json` into a new
temporary directory outside the repository.

- [ ] **Step 2: Run the clean-install acceptance test**

Run `npm ci --no-audit --no-fund` followed by `npm ls --depth=0 --json` in the
fixture.

Expected: both commands exit zero and the JSON contains no `problems` field.

- [ ] **Step 3: Verify the normal frontend workflow**

Run:

```powershell
npm test
npm run lint
npm run build
```

Expected: all commands exit zero.

### Task 4: Complete Repository Verification And Records

**Files:**

- Modify: `docs/superpowers/plans/2026-08-06-dependency-and-plan-lifecycle.md`

- [ ] **Step 1: Run focused workflow regressions**

Run:

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py tests/developer_workflow/test_plan_lifecycle.py tests/developer_workflow/test_worktree_deps.py
```

Expected: PASS, with only documented platform skips.

- [ ] **Step 2: Run complete commit verification**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1
```

Expected: PASS.

- [ ] **Step 3: Mark this plan complete**

Change this plan's status to `completed`, check every step, and add a completion
record with the fresh-install, frontend, workflow, and repository verification
results.

- [ ] **Step 4: Inspect and commit**

Run `git diff --check`, inspect the complete diff, stage only the files named in
this plan, and create focused commits for the dependency contract and plan
lifecycle records.
