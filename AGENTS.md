# Codex Project Instructions

## Development Scope

This repository is now past the large-version maintenance baseline. New feature
work is allowed, but it must still preserve the architecture boundaries created
during maintenance.

- Use small vertical slices. Do not combine learning review, source import
  expansion, chat history, and web-source backfill in one change.
- Prefer an end-to-end MVP slice before broad horizontal expansion.
- Keep legacy compatibility paths working unless there is an explicit removal
  plan, tests, and migration note.
- Do not move business logic back into routers, large React containers, or mixed
  structure-test files for convenience.

## Task Risk Tiers

Classify a change before choosing its workflow. If any condition is unclear,
use the next higher tier.

### Micro task fast lane

A task qualifies only when it changes at most three production files, is easy
to revert, adds no dependency, stays within one frontend or backend boundary,
and does not alter APIs, persisted data, authentication, authorization, or
security behavior.

- Do not create an independent design spec or implementation plan. Record the
  problem, root cause, change, out-of-scope behavior, acceptance, and exact
  verification using `docs/micro-task-template.md` or the task/commit body.
- Work directly in the current checkout only when it is clean. If unrelated
  changes are present, use a worktree so the micro task remains isolated.
- Add a failing targeted test first for behavior or boundary changes. Pure
  documentation, comments, or visual-value-only edits may omit a new automated
  test when the task record explains why.
- Run `scripts\verify-fast.ps1` with explicit test and lint targets. Inspect only
  the affected page, state, and viewport; check desktop and mobile only when a
  responsive rule changes.
- Finish with one focused commit.

### Normal task

New interactions, component splits, multi-state behavior, or changes spanning
four to ten production files require a short design note, an isolated worktree,
targeted tests, and rendered checks for affected viewports.

### High-risk task

Changes to data models, authentication, security, APIs, migrations,
dependencies, deployment, or cross-platform releases require the full design,
implementation plan, test-driven workflow, complete verification, and relevant
release checklist.

The fast lane does not replace `scripts/verify-before-commit.ps1` for normal or
high-risk work, releases, deployments, shared build configuration, or any task
whose targeted checks reveal cross-module impact. CI remains the final full
verification gate after integration.

## Worktree Flow

Use an isolated worktree by default for feature, refactor, or maintenance
slices, especially when touching production code, tests, migrations, build
scripts, generated assets, or more than one subsystem.

Small, low-risk changes may be made directly in the current checkout when a
worktree would add process overhead without protecting meaningful state. This
includes narrow documentation edits, typo fixes, comment-only changes, or small
configuration/instruction updates that do not require running the full
implementation workflow. For these changes, still inspect the working tree first
and run the lightest relevant verification such as `git diff --check`.

1. Create the branch under `.worktrees/<slice-name>`.
2. Confirm the baseline with targeted tests before editing.
3. Write or update the failing test/guard first for behavior or boundary
   changes.
4. Make the smallest implementation that satisfies the test.
5. Run targeted regressions in the worktree.
6. Run the full commit verification before committing.
7. Merge back to `main` with `git merge --ff-only`.
8. Re-run targeted regressions on `main`.
9. Remove the worktree and branch.

If `frontend/node_modules` is needed only for verification inside a temporary
worktree, install it there, then remove it before removing the worktree. Never
stage generated dependencies or build output.

## File Boundary Rules

Backend boundaries:

- `app/routers/*` should contain FastAPI parameters, dependency injection,
  DTOs, compatibility wrappers, and service delegation only.
- Route orchestration belongs in `app/services/*_runtime.py`.
- Pure response shaping, item mapping, and display payload rules belong in
  `app/services/*_presenters.py` or focused helper modules.
- RAG behavior should stay split by domain:
  - `rag_runtime_components.py` for construction of embeddings, vectorstore,
    LLM, splitters, and prompts.
  - `rag_indexing.py` for vector indexing/write behavior.
  - `rag_search.py` for vector search/filter behavior.
  - `rag_qa.py` for answer orchestration.
  - `rag_summary.py` for summarization chain behavior.
  - `rag_collection_ops.py` for low-level collection operations.
- Source binding and favorite-folder rules should reuse shared presenters and
  service helpers. Do not duplicate invalid-video, default-folder, or organize
  candidate rules across legacy and scoped paths.

Frontend boundaries:

- `ChatPanel.tsx` should remain an orchestrating shell, not a place for stream
  reading, model config logic, web-search config persistence, history mapping,
  viewport math, or large section JSX.
- Streaming network/runtime logic belongs in
  `frontend/components/chat/chatStreamingRuntime.ts`.
- Streaming state transitions belong in
  `frontend/components/chat/chatStreamingState.ts`.
- Chat UI sections belong in focused section components such as
  `ChatPanelHeader.tsx` and `ChatPanelComposerSection.tsx`.
- Scope picker UI should stay in `frontend/components/chat-scope/*` focused
  components.
- Shared provider metadata belongs in `frontend/lib/providers.ts`, not inside
  panels.

## Structure Test Rules

Structure tests are boundary guards, not behavior test dumping grounds.

- Keep sentinel files light. If a structure test file grows into mixed domains,
  split it into focused files and add a split guard.
- `tests/frontend_structure/test_chat_component_boundaries.py` is intentionally
  a lightweight sentinel. Chat-specific structure checks belong in the focused
  files beside it.
- `tests/service_boundaries/*` should guard backend ownership boundaries and
  prevent router/service logic from flowing back to the wrong layer.
- When introducing a new architectural boundary, add or update a structure guard
  that prevents the old anti-pattern from returning.
- Prefer checking imports, file existence, public function placement, and
  absence of known implementation tokens over brittle formatting assertions.

## New Feature Entry Points

Learning review features:

- Start with one vertical MVP: source selection, summary/review generation,
  persistence if needed, and minimal UI access.
- Reuse knowledge-base, chat, RAG, source binding, and presenter services before
  creating new abstractions.
- Do not put learning-review orchestration directly into routers or ChatPanel.

Source import expansion:

- Extend source binding/service abstractions first.
- Reuse shared favorite/source presenter rules when possible.
- Keep provider-specific API quirks in provider services, not routers or generic
  UI components.

Chat history and web-source backfill:

- Keep history persistence in focused hooks/services.
- Keep streaming, fallback, and source trailer parsing inside the existing chat
  runtime/state boundaries.
- Add regression coverage for source visibility and regeneration behavior before
  changing UI orchestration.

## Stable Commit Workflow

Before creating a git commit in this repository, run the commit checks in this order.

1. Inspect the worktree:

   ```powershell
   git status --short
   git diff --check
   ```

2. Format changed files before committing:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
   ```

3. Run verification:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
   ```

4. Stage files explicitly. Do not stage local secrets, generated data, or build/cache output:

   - `.env.local`
   - `data/`
   - `logs/`
   - `frontend/.next/`
   - `frontend/out/`
   - `frontend/node_modules/`
   - `frontend/android/**/build/`
   - `__pycache__/`
   - `.pytest_cache/`

5. After staging, run:

   ```powershell
   git diff --cached --check
   git diff --cached --name-only
   ```

6. Commit normally and let the pre-commit hook run. If the hook fails, read the failure and fix formatting or tests first. Do not skip hooks unless the hook itself is demonstrably wrong and equivalent checks have already passed.

7. After commit, verify:

   ```powershell
   git log -1 --oneline
   git status --short
   ```

## Expected Checks

The local verification script runs:

- Python formatting check with Black.
- Backend tests with `python -m pytest -q`.
- Frontend Prettier checks for staged/changing web files.
- Frontend `npm run lint`.
- Frontend tests.
- Frontend production build.
- Git whitespace checks.

For risky or broad changes, prefer the full verification path even if only a few files changed.

## Production Release And Deployment

The source of truth for production releases is
`docs/deployment/container-production.md`. Read it before changing deployment
infrastructure, publishing images, operating the ECS host, restoring data, or
giving production deployment instructions.

For a requested release from the development checkout:

1. Inspect the worktree and the staged diff. Never stage or commit unrelated
   user changes, local secrets, generated data, dependencies, or build output.
2. Run the checks required by `Stable Commit Workflow`. Fix failures instead of
   bypassing hooks or weakening CI.
3. Push only when the user explicitly requests publication. After pushing
   `main`, monitor both `CI` and the downstream `Publish Images` workflow for the
   exact commit.
4. Treat a skipped, cancelled, or failed workflow as a failed release. Do not
   deploy from `latest`, from a local build, or from a commit whose two SHA image
   tags were not successfully published and verified.
5. Report the full 40-character lowercase Git SHA selected for deployment. The
   backend and frontend must use the same SHA.

Production deployment remains a manual approval gate. A release request does
not authorize an agent to SSH to ECS or change the running service. Only perform
server deployment when the user explicitly requests it and server access is
available. On ECS:

1. Use the fixed deployment root `/opt/zhiku-cloud` and the same operating-system
   account used for ACR login, deployment, restore, and recovery.
2. Before deployment, recover an existing `deploy/transaction`, check disk
   capacity, confirm the exact SHA exists in both ACR repositories, and preserve
   the active `.env.deploy`, `.env.production`, certificate paths, `data`,
   `backups`, and `logs`.
3. Deploy only with `./scripts/deploy.sh <40-character-sha>`. Do not reproduce
   its behavior with ad hoc `docker compose` commands.
4. Verify Compose status, backend and frontend logs, local health endpoints on
   `127.0.0.1:8000` and `127.0.0.1:3000`, and the public HTTPS health endpoint
   before reporting success.
5. On failure, preserve transaction markers and safety directories and follow
   the documented recovery or rollback procedure. Never delete production data
   to make a retry pass.

Never commit production secrets, copy production environment files back to the
development machine, expose ports 3000 or 8000 publicly, overwrite an existing
40-character ACR tag, or delete old deployment/data/backup paths before backup
and business acceptance are confirmed. Infrastructure updates may synchronize
reviewed Compose, script, and Nginx example files, but must not overwrite active
host environment files or certificate configuration.
