# Developer Workflow Latency Design

**Date:** 2026-07-30  
**Status:** Approved for implementation planning

## Problem

The first optimization batch added a safe micro-task fast lane, but three
frequent workflow costs remain outside that verifier:

1. The user-level Git pre-commit hook checks files one at a time and invokes
   `npx --yes prettier`, which may download an unpinned tool during a commit.
2. Pull-request CI runs both backend and frontend jobs even when a change cannot
   affect one of those areas. The backend job also lacks a pip dependency cache.
3. Temporary worktrees repeat a full frontend dependency installation even when
   their manifests are identical to the main worktree.

The second batch reduces those costs without weakening the full verification
boundary used after integration.

## Goals

- Make the global pre-commit hook deterministic, batched, NUL-safe, and free of
  implicit network installs.
- Let this repository opt into a version-controlled staged-file checker while
  retaining a safe generic fallback for other repositories.
- Skip unrelated heavy CI jobs on pull requests while keeping full CI on pushes
  to `main` and `release/**`.
- Reuse the main worktree's frontend dependencies when exact compatibility can
  be proven, with an isolated `npm ci` fallback.
- Keep every cleanup operation bounded and fail closed when path or ownership
  cannot be proven.

## Non-goals

- Migrating npm to pnpm or another package manager.
- Reducing E2E coverage for frontend-related pull requests.
- Selecting individual tests based on guessed dependency graphs.
- Sharing or rebuilding Python virtual environments per worktree.
- Auto-formatting or mutating the Git index from a pre-commit hook.

## Architecture

### 1. Global hook as an opt-in dispatcher

The global hook at `C:/Users/amui/.git-hooks/pre-commit` remains the entry point
for every repository. It does not automatically execute a similarly named file
from an arbitrary checkout. A repository must opt in through local Git config,
using a Boolean key:

```text
workflow.useRepositoryHook = true
```

The installer for this repository sets that local key. When it is exactly
`true`, the global hook invokes the fixed, repository-relative
`scripts/verify-staged.ps1` entry point from the repository root. It never
evaluates a command stored in Git config. When the key is absent or false, the
hook uses its generic fallback.

Both paths read staged file names from
`git diff --cached --name-only -z --diff-filter=ACMR`. The generic fallback:

- batches all Python paths into one Ruff or Black invocation;
- falls back to `python -m py_compile` when neither formatter is installed;
- batches web and documentation paths into one locally installed Prettier
  invocation;
- never invokes `npx --yes` or downloads a missing tool;
- warns and skips a formatter whose executable cannot be resolved; and
- fails the commit when an executed check fails.

The external hook update is installed atomically. Before replacement, the
installer writes a timestamped backup next to the existing hook and reports the
exact restore command. Repository tests exercise a fixture copy, not the live
user-level hook.

### 2. Repository staged-file checker

`scripts/verify-staged.ps1` owns this project's commit-time checks. It performs:

1. `git diff --cached --check`;
2. one Black check over all existing staged Python files; and
3. one project-local Prettier check over all existing staged web and
   documentation files.

Prettier becomes a pinned frontend development dependency and is invoked through
`frontend/node_modules/.bin`, never through package-runner download behavior.
The checker treats staged names as literal repository-relative paths, rejects
paths outside the repository and symbolic-link targets, and preserves special
characters through NUL-delimited enumeration.

The hook intentionally does not run pytest, Vitest, ESLint, or a production
build. Those checks belong to `verify-fast.ps1`,
`verify-before-commit.ps1`, and CI; repeating them during `git commit` would add
latency without adding a new verification boundary.

### 3. Pull-request CI path routing

CI gains a small repository-owned path classifier. A `changes` job supplies the
pull-request base and head revisions and publishes three Boolean outputs:

- `backend`: backend source, backend tests, Python requirements, deployment
  scripts, or shared verification policy changed;
- `frontend`: frontend source, frontend dependencies, frontend tests, or shared
  CI configuration changed; and
- `docs_only`: every changed path is documentation or other explicitly static
  text that is not consumed by a contract test.

Policy sources asserted by tests, including `AGENTS.md`, `CLAUDE.md`, the
micro-task template, and fast-lane specifications, are classified as shared
verification changes rather than documentation-only changes and trigger the
backend job.

The backend and frontend jobs use those outputs only for pull requests. Pushes
to `main` and `release/**` force both outputs true and therefore run the complete
pipeline. A final `ci-success` job uses `always()` and validates the result of
every job that was required to run, so a skipped job cannot hide a failure or
leave branch protection waiting indefinitely.

The backend setup enables the official `setup-python` pip cache keyed by
`requirements.txt`. The existing npm cache remains. Frontend-related pull
requests still install Playwright and run lint, unit tests, production build,
and E2E tests.

No third-party changed-files action is introduced. The classifier is a small
script with table-driven tests, keeping path policy reviewable in this
repository.

### 4. Conditional worktree dependency reuse

`scripts/worktree-deps.ps1` exposes three modes:

- `Prepare`: reuse compatible dependencies or install isolated dependencies;
- `Status`: report shared, isolated, missing, or unsafe state; and
- `Detach`: safely remove only a verified shared dependency junction.

`Prepare` first proves that the target is a registered worktree located beneath
the repository's `.worktrees` directory. It then:

- confirms that the current Node executable is runnable;
- compares `frontend/package.json` and `frontend/package-lock.json` byte for
  byte; and
- runs `npm ls --depth=0` in the main frontend directory to verify that the
  reusable installation satisfies its manifest.

If the manifests match and the main worktree has `frontend/node_modules`, the
script creates a Windows directory junction from the temporary worktree to that
directory. If compatibility cannot be proven, it runs `npm ci` inside the
temporary worktree instead.

While a junction is active, dependency-mutating commands such as `npm install`
and `npm ci` are prohibited by policy. A task that changes either manifest must
first detach the junction and prepare isolated dependencies.

`Detach` resolves and validates the junction target before removal. It refuses
to remove a normal directory, an unexpected reparse point, a target outside the
known main dependency directory, or any path outside the registered temporary
worktree. It removes only the junction entry and never recursively deletes the
target. Worktree cleanup instructions call `Detach` before `git worktree
remove`.

## Error handling

- Missing project-local tools fail the repository-specific hook with a command
  that prepares dependencies.
- Missing tools in the generic global fallback produce a warning and no network
  access; checks that can run still run.
- Invalid staged paths, link targets, malformed NUL-delimited output, and
  subprocess failures stop the commit.
- CI classification errors fail the `changes` job and therefore fail the final
  summary job.
- Worktree dependency operations refuse ambiguous or unsafe states. They never
  guess a main path or delete a directory they did not create as a verified
  junction.

## Testing

### Hook contracts

Isolated Git repositories cover:

- an empty staged set;
- spaces, Unicode, newlines, and glob characters in file names;
- one batched invocation per tool;
- project-specific opt-in dispatch;
- missing-tool fallback without `npx --yes` or network access;
- non-zero formatter propagation; and
- installer backup and restore instructions using a fixture hook directory.

### CI classifier contracts

Table-driven tests cover backend-only, frontend-only, documentation-only,
workflow, dependency, verification-script, and mixed changes. Workflow changes
require both heavy jobs. Push-mode tests require both jobs regardless of paths.

### Worktree contracts

Temporary repositories and worktrees cover compatible reuse, manifest mismatch,
missing main dependencies, Node-version mismatch, idempotent status, a normal
directory at the junction path, an unexpected junction target, paths outside
`.worktrees`, and safe detach behavior.

### Final verification

The implementation must pass:

- the new focused hook, CI-classifier, and worktree tests;
- the existing fast-workflow contract suite;
- `python -m pytest -q`;
- frontend lint and unit tests;
- frontend production build;
- workflow YAML validation; and
- `git diff --check` plus staged diff checks.

## Acceptance criteria

- The global hook contains no implicit package download command.
- A staged set invokes each formatter at most once.
- The repository-specific hook uses pinned local Prettier and completes a warm
  formatting-only check in a few seconds.
- A documentation-only pull request runs classification and summary jobs but no
  backend or frontend heavy job.
- Pushes to `main` and `release/**` run both complete jobs.
- A compatible worktree reuses dependencies without running `npm ci` and
  prepares in under five seconds on the target Windows environment.
- Manifest mismatch reliably selects an isolated install.
- Cleanup cannot delete the main worktree's dependency directory.

## Rollback

- Restore the timestamped global-hook backup and unset
  `workflow.useRepositoryHook` in the repository-local Git config.
- Revert the CI routing commit to return to unconditional jobs.
- Run `worktree-deps.ps1 -Mode Detach` before removing the helper; isolated
  `node_modules` directories remain ordinary worktree-local data.
