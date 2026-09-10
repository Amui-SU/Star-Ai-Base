# YAML Development Dependency Advisory Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** completed

**Goal:** Upgrade the root `yaml` development security pin from 2.8.1 to 2.9.0 and pin the patched transitive releases newly required by the live npm advisory database so both production and full audits report zero vulnerabilities.

**Architecture:** Preserve the existing root exact-pin mechanism used by the Vitest/Vite dependency tree. Add a manifest/lock contract first, detach shared worktree dependencies before any npm mutation, regenerate only the two dependency files with npm 10.9.2, and accept the change only after fresh installation, complete local verification, independent review, and exact-SHA remote CI.

**Tech Stack:** Node.js 22.13.1 baseline, npm 10.9.2, npm lockfile v3, pytest, Vitest, Next.js 16, Playwright, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-01-yaml-advisory-remediation-design.md`

## Global Constraints

- Keep `yaml` as an exact root dev dependency and set it to exactly `2.9.0`.
- Apart from `yaml`, change only the two patched transitive dependencies and
  the browser-database packages required by patched Browserslist; do not use
  `npm audit fix --force`.
- Use exact overrides for `browserslist@4.28.8` and
  `@xmldom/xmldom@0.9.12`; do not add an audit exception or weaken either CI
  audit gate.
- Detach the shared `frontend/node_modules` junction before running any npm install or dependency mutation command in this worktree.
- Use npm 10.9.2 to regenerate the lockfile and preserve lockfile version 3.
- On this host, invoke the exact CLI as `npx --yes npm@10.9.2`; the PATH npm
  is 11.6.1 and Corepack cannot install across its Windows cache volumes.
- Do not merge pull request 7 into `main` and do not deploy production.

---

### Task 1: Pin The Patched YAML Release With A Reproducible Lockfile

**Files:**

- Modify: `tests/developer_workflow/test_frontend_dependency_contract.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**

- Consumes: the root `devDependencies`, lockfile root package, and `node_modules/yaml` lock entry.
- Produces: an exact `yaml@2.9.0` security pin shared by the Vitest/Vite tree and a contract preventing manifest/lock drift.

- [x] **Step 1: Detach the shared dependency junction**

From the worktree root, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Detach
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/worktree-deps.ps1 -Mode Status
```

Require `state=missing` before any `npm install`, `npm ci`, or lockfile mutation.

- [x] **Step 2: Add the failing exact-pin contract**

Add the following constant and test to
`tests/developer_workflow/test_frontend_dependency_contract.py`:

```python
SECURITY_PINNED_DEV_DEPENDENCIES = {"yaml": "2.9.0"}


def test_security_pinned_dev_dependencies_are_exact_and_locked():
    manifest = load_json(FRONTEND_ROOT / "package.json")
    lockfile = load_json(FRONTEND_ROOT / "package-lock.json")

    for name, version in SECURITY_PINNED_DEV_DEPENDENCIES.items():
        assert manifest["devDependencies"][name] == version
        assert lockfile["packages"][""]["devDependencies"][name] == version
        assert lockfile["packages"][f"node_modules/{name}"]["version"] == version
```

- [x] **Step 3: Run the contract and verify RED**

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py
```

Expected: the new test fails because all three observed values are `2.8.1`
rather than `2.9.0`.

- [x] **Step 4: Verify the pinned toolchain**

```powershell
node --version
npx --yes npm@10.9.2 --version
```

Require Node to satisfy `.nvmrc`/`engines` and npm to report exactly `10.9.2`.
If npm differs, stop and resolve the pinned local tool path rather than
regenerating the lockfile with another npm version.

- [x] **Step 5: Update only the exact YAML dependency**

From `frontend/`, run:

```powershell
npx --yes npm@10.9.2 install --save-dev --save-exact yaml@2.9.0 --no-audit --no-fund
```

Then inspect:

```powershell
git diff -- frontend/package.json frontend/package-lock.json
```

Require the manifest and lockfile root to contain exact `2.9.0`, the
`node_modules/yaml` entry to use the 2.9.0 registry artifact, lockfile version
to remain 3, and no unrelated package resolution to change.

- [x] **Step 6: Run the contract and verify GREEN**

```powershell
python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py tests/test_dependency_security_policy.py
```

Require every test to pass and the exception register to remain free of active
exceptions.

- [x] **Step 6a: Address advisories published during final review**

The live 2026-09-03 audit added high advisories for the baseline
`browserslist@4.28.4` and a moderate advisory for baseline
`@xmldom/xmldom@0.9.10`. Add a failing transitive-pin contract, then exact
manifest overrides for patched `browserslist@4.28.8` and
`@xmldom/xmldom@0.9.12`. Regenerate the lockfile with npm 10.9.2 and require
the focused contract/security suite to pass.

- [x] **Step 7: Verify a fresh reproducible dependency tree**

From `frontend/`, run:

```powershell
npx --yes npm@10.9.2 ci --no-audit --no-fund
npx --yes npm@10.9.2 ls --depth=0 --json
npx --yes npm@10.9.2 ls yaml --all
npx --yes npm@10.9.2 audit --omit=dev --audit-level=high
npx --yes npm@10.9.2 audit --audit-level=high
```

Require `npm ci` and both `npm ls` commands to exit zero, no `problems` array,
only `yaml@2.9.0` in the YAML tree, and zero vulnerabilities in both audits.

- [x] **Step 8: Run complete local verification and browser tests**

From the worktree root, use the Python 3.12 Black module for the full verifier:

```powershell
$env:VITEST_MAX_THREADS='4'
$env:VITEST_MIN_THREADS='1'
function black { & python -m black @args }
& ./scripts/verify-before-commit.ps1 -Format -SkipBackendTests
& ./scripts/verify-before-commit.ps1
```

Then from `frontend/` run:

```powershell
npm run test:e2e -- --workers=1
```

Require backend tests, frontend tests, lint, build, formatting, whitespace, and
all browser tests to pass. Record exact counts and warnings.

- [x] **Step 9: Request independent review**

Review the full dependency diff and verification evidence. The first review
found the newly published audit failures described in Step 6a. Fix every
Critical or Important finding, repeat the affected focused checks plus complete
verification after any dependency change, and obtain a clean follow-up review.

- [x] **Step 10: Commit the dependency remediation**

```powershell
git add tests/developer_workflow/test_frontend_dependency_contract.py frontend/package.json frontend/package-lock.json
git diff --cached --check
git commit -m "build: update patched yaml security pin"
```

Let the normal pre-commit hook run; do not bypass it.

#### Task 1 execution record

- Dependency state was `missing` before mutation and `isolated` after the fresh
  install.
- Runtime: Node `v24.11.0` (allowed by repository engines); lockfile operations:
  npm `10.9.2` via `npx --yes npm@10.9.2`.
- TDD red: the YAML contract failed against `2.8.1`; after the 2026-09-03
  advisory change, the transitive contract failed because the two overrides
  were absent.
- Focused green: dependency contract plus security policy `6 passed`; plan
  lifecycle and index tests `16 passed`.
- Fresh install: `627` packages; root dependency tree exited zero without a
  `problems` array. The resolved security tree contains `yaml@2.9.0`,
  `browserslist@4.28.8`, and `@xmldom/xmldom@0.9.12` only at their expected
  paths.
- Both the production and complete npm audits reported `0 vulnerabilities`.
- Final verifier: backend `1566 passed, 6 skipped, 2 warnings`; frontend lint
  passed, Vitest `377 passed`, and the Next.js production build passed.
- Playwright with one worker: `3 passed`.
- Independent review round one found the newly published baseline
  Browserslist/xmldom advisories. After remediation, round two found no
  High/Medium issue; its single Low wording correction was applied.
- Dependency remediation commit: `f14fbbe` (`build: update patched frontend
security dependencies`). The normal pre-commit hook passed without bypass.

### Task 2: Integrate, Verify Remote CI, And Close The Follow-Up

**Files:**

- Modify: `docs/superpowers/plans/2026-09-01-yaml-advisory-remediation.md`
- Modify: `docs/superpowers/plans/README.md`
- Update externally: pull request 7 description

**Interfaces:**

- Consumes: the clean dependency commit, local verification evidence, GitHub CI, and pull request 7.
- Produces: a completed indexed plan, clean release branch, current PR audit facts, and exact-SHA CI evidence.

- [x] **Step 1: Record local evidence with partial status**

Mark Task 1 complete, set this plan to `partial`, record the exact Node/npm
versions, install/audit/tree results, test counts, browser result, review
verdict, and dependency commit. Regenerate and verify the plan index:

```powershell
python scripts/generate-plan-index.py
python scripts/generate-plan-index.py --check
python -m pytest -q tests/developer_workflow/test_plan_lifecycle.py tests/developer_workflow/test_plan_index_generator.py
```

Commit the partial verification record normally.

- [x] **Step 2: Fast-forward into the release branch**

Require both checkouts clean. From the main repository checkout on
`release/video-security-integration-20260729`, run:

```powershell
git merge --ff-only chore/yaml-advisory-remediation
```

Repeat the focused dependency contract, security policy, fresh npm tree, and
both audit commands on the integrated result, using the exact npm 10.9.2
invocations from Task 1.

- [x] **Step 3: Push and require both exact-SHA CI events**

Push without force. Require the push and pull-request workflow runs for the
exact dependency SHA to complete `Changes`, `Backend`, `Frontend`, and
`CI Success` successfully. A skipped, failed, or cancelled expected job fails
this gate.

- [x] **Step 4: Update pull request 7 facts**

Remove the resolved moderate YAML advisory from the non-blocking follow-ups.
Record the exact dependency SHA, zero-vulnerability production and full audit
results, and links to both successful CI runs. Keep the PR Open and Ready; do
not merge it into `main`.

- [x] **Step 5: Close the plan after remote acceptance**

Set status to `completed`, check every step, record the CI run IDs and PR state,
regenerate the index, run the two plan tests from Step 1, and commit the closure
record. Fast-forward and push that documentation commit, then require its push
and pull-request CI runs to pass. Record those final run links in the handoff
instead of creating a self-referential documentation commit.

#### Task 2 execution record

- The release branch fast-forwarded cleanly from `298546b` to `0eacbdc`; its
  fresh npm 10.9.2 installation, focused `6 passed` checks, dependency tree,
  production audit, and complete audit all passed.
- Exact SHA `0eacbdcebbadcc43abe8ab0b48b3809858501492`
  passed push run `33763152626` and pull-request run `33763157819`. Both runs
  completed `Changes`, `Backend`, `Frontend`, and `CI Success` successfully.
- Pull request 7 was updated to remove the resolved YAML follow-up and record
  all three patched dependency versions, zero-vulnerability audits, and both
  successful runs. It remained Open, Ready, and CLEAN; it was not merged into
  `main`, and no deployment was performed.
- The closure commit's push and pull-request run links are intentionally
  recorded in the final handoff rather than this file, avoiding a
  self-referential documentation commit.
