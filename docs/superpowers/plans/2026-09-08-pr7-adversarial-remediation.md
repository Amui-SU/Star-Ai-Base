# PR 7 Adversarial Remediation Implementation Plan

**Status:** completed

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Close the six Important findings recorded in the approved PR 7 design.

**Architecture:** Deliver authentication and gateway changes as batch 1, followed by frontend concurrency and CI routing as batch 2. Preserve service boundaries and use database-side credential versions and counters; frontend state changes remain in focused hooks and pure helpers.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, SQLite, React, TypeScript, Vitest, pytest, Nginx.

**Spec:** ../specs/2026-09-03-pr7-adversarial-remediation-design.md

## Global Constraints

- Existing API payloads remain compatible; SMTP delivery failure returns the generic reset-send response.
- Credential versions use `INTEGER NOT NULL DEFAULT 0` for legacy rows.
- Poll requests time out after 10 seconds, retry after 2 seconds, stop after 5 consecutive failures, and stop tracking after 2 hours.
- HTTP 401, 403, and 404 terminate local tracking immediately.
- Shared frontend dependencies must not be installed or updated in this worktree.
- Normal hooks and full verification remain required for implementation commits.
- Integrate into the existing release branch, keep PR 7 open, and verify push and PR CI for the final SHA. Production deployment is outside this task.

## Task 1: Reset delivery privacy (batch 1)

**Files:** `app/services/system_auth_password_reset.py`, `tests/system_auth/test_password_reset.py`.

**Interface:** `send_password_reset_code(...) -> dict[str, str]` retains its public signature.

- [x] Change the SMTP failure test to compare the returned response with an unknown-account response; parameterize false return and raised transport exception. Verify the reserved code is absent and a later send can succeed.

  ```python
  assert response == {"message": "如果该邮箱已注册，重置验证码已发送"}
  assert count == 0
  ```

- [x] Run `python -m pytest -q tests/system_auth/test_password_reset.py -k delivery_failure` and observe the old 500/exception failure.
- [x] Catch delivery exceptions at the delivery boundary, log a fixed diagnostic without recipient/code/exception text, delete only the reservation ID/hash, commit cleanup, and return the generic response.
- [x] Run the complete password reset test file.

## Task 2: Credential epochs (batch 1)

**Files:** `app/models.py`, `app/services/sqlite_legacy_schema.py`, `app/services/system_auth_sessions.py`, `app/services/system_auth_login.py`, `app/services/system_auth_registration.py`, `app/services/system_auth_oauth_flow.py`, `app/services/system_auth_password_reset.py`, `app/services/system_auth_admin.py`, `app/dependencies.py`. Tests: create `tests/system_auth/test_credential_versions.py` and `tests/test_sqlite_credential_version_migration.py`.

**Interface:** `create_system_session(db, user_id, response, *, credential_version: int)` requires the version observed during authentication. Both resolvers join session/user and require version equality.

- [x] Add a real independent-session interleaving test: pause login after password verification, reset using another session, release login, and assert its token is rejected by both resolvers. Add admin reset and fresh login coverage.

  ```python
  with pytest.raises(HTTPException) as failure:
      await resolve_current_user(request, db)
  assert failure.value.status_code == 401
  ```

- [x] Add migration tests creating legacy user/session rows, run migration twice, and assert old and subsequently inserted rows default to version 0. Run both new files and observe failure.
- [x] Add non-null integer columns with Python/server defaults, pass observed versions through every session creation path, and atomically increment user version alongside password changes.

  ```python
  credential_version = Column(Integer, default=0, server_default="0", nullable=False)
  # UPDATE values for password changes:
  credential_version=SystemUser.credential_version + 1
  ```

- [x] Query session and active user together with version equality and populate existing ORM objects from the query so cached objects cannot conceal a reset.
- [x] Run `python -m pytest -q tests/system_auth tests/test_system_auth.py tests/test_sqlite_credential_version_migration.py tests/test_sqlite_password_reset_migration.py`.

## Task 3: Atomic send quota and gateway coverage (batch 1)

**Files:** `app/services/system_auth_codes.py`, `deploy/nginx/zhiku-cloud.conf.example`, `tests/system_auth/test_email_codes.py`, `tests/test_container_deployment.py`; create `tests/system_auth/test_rate_limit_concurrency.py`.

**Interface:** `check_ip_rate_limit(db, client_ip) -> bool` retains its public signature and commits the decision.

- [x] Add independent-session concurrent quota tests for a new, active, and expired IP, asserting exactly three grants and persisted count 3; include a preloaded stale ORM object to expose lost updates deterministically.

  ```python
  results = await asyncio.gather(*(attempt() for _ in range(8)))
  assert results.count(True) == 3
  assert results.count(False) == 5
  ```

- [x] Extend the Nginx location contract to resolve both send paths and optional trailing slashes to the rate-limited block; assert unrelated auth paths use the ordinary proxy. Observe red tests before changing implementation.
- [x] Use conditional UPDATE/RETURNING with SQL CASE for expiry and count, insert a missing IP inside a savepoint, retry unique conflicts at most three times, and fail closed on exhausted contention. Preserve expired unrelated-row cleanup.
- [x] Use `location ~ ^/system-auth/(?:password-reset/)?send-code/?$` with existing zone and proxy settings.
- [x] Run auth, migration, deployment, and service-boundary regressions; format changed files, run full verifier, review batch 1, and commit explicitly scoped files normally.

## Task 4: AI conflict detection (batch 2)

**Files:** `frontend/components/video-notes/useVideoNoteAiEditing.ts`, `VideoNoteWorkspace.tsx`; create `videoNoteAiConflicts.ts` and its test beside the hook, extend `useVideoNoteAiEditing.test.tsx` and workspace tests.

**Interface:** `hasVideoNoteAiConflict(start: VideoNoteBlock[], current: VideoNoteBlock[], operations: VideoNoteAiOperation[]): boolean`; `applyAiOperations(operations, startingBlocks?) -> boolean` returns false for conflict without state/undo changes.

- [x] Add delayed-response tests preserving unrelated manual edits, rejecting changed/deleted targets, rejecting whole-document replacement after edits and insert-ID collisions, and restoring the exact pre-application state on undo.

  ```typescript
  expect(result.current.applyAiOperations(operations, startingBlocks)).toBe(
    false,
  );
  expect(result.current.undoDepth).toBe(0);
  ```

- [x] Run targeted Vitest tests to red. Capture request-start blocks, compare operation targets using a pure helper, apply accepted operations to latest committed blocks, and use latest callbacks.
- [x] On conflict, show a regenerate message and do not apply tags or success metadata. Keep note/request guards and overwrite confirmation.
- [x] Run hook/helper/workspace tests and targeted lint.

## Task 5: Bounded polling (batch 2)

**Files:** `frontend/lib/api/client.ts`, `frontend/lib/api/imports.ts`, API barrel as needed, `frontend/components/import-modal/useImportTaskTracking.ts`; create focused polling/API tests and keep `useImportModal.tasks.test.ts` green.

**Interfaces:** `ApiError extends Error` exposes numeric `status`; `importApi.taskStatus(taskId: string, signal?: AbortSignal)` forwards the signal.

- [x] Add fake-timer tests with controllable promises for never-settling requests, permanent status failures, transient recovery and retry exhaustion, two-hour tracking, callback/batch changes, duplicate tasks, and unmount cancellation. Add HTTP-client tests proving status/message and signal behavior.

  ```typescript
  await act(() => vi.advanceTimersByTimeAsync(10000));
  expect(signal.aborted).toBe(true);
  // After five failed attempts no later request is issued.
  expect(result.current.taskProgress[0].status).toBe("interrupted");
  ```

- [x] Run new tests to red. Own controllers/timers by hook lifetime; batch/callback renders must not abort another poll. Race transport with a timeout rejection so an abort-ignoring promise cannot retain the in-flight slot.
- [x] Apply the exact limits in Global Constraints, reset failure count on matching valid response, and keep local interruption in memory. Cleanup aborts controllers, clears timers, and prevents stale state writes/retries.
- [x] Run polling/API/modal tests and lint.

## Task 6: CI routing and closeout (batch 2)

**Files:** `scripts/classify-ci-paths.py`, `tests/developer_workflow/test_ci_paths.py`, this plan and generated plan index.

**Interface:** `classify_paths(paths, force_full=False)` keeps its response shape.

- [x] Add routing cases for security/deployment/spec/unknown documents, retaining root README docs-only and plan backend coverage. Observe red.

  ```python
  assert classifier.classify_paths(["docs/security/exception.md"]) == {
      "backend": True, "frontend": True, "docs_only": False
  }
  ```

- [x] Replace suffix fallback with exact `README.md` allowlist; explicit security/deployment/spec prefixes require both jobs.
- [x] Run CI/workflow/dependency-policy/plan tests, frontend lint/tests/build and Playwright, full verifier, and independent adversarial review. Fix material findings with regression tests.
- [x] Commit batch 2 with normal hooks; fresh dependency installation in an isolated temporary directory uses npm 10.9.2 and verifies tree/audits without touching shared dependencies.
- [x] Integrate and push the release branch; validate push and PR workflows for final SHA. Update plan status/checklist and regenerate index using `python scripts/generate-plan-index.py` when the behavior is integrated.

## Task 7: Approved dependency security batch (2026-09-10)

**Files:** `frontend/package.json`, `frontend/package-lock.json`,
`tests/developer_workflow/test_frontend_dependency_contract.py`, this plan,
the associated design addendum, and generated plan index.

**Contract:** keep Node 22.13.1 and npm 10.9.2; pin Next.js/eslint-config-next
16.3.4, sharp/sharp-wasm 0.35.4, @emnapi/runtime 1.11.3, Vitest 4.1.11,
and js-yaml 4.3.2. Keep Vite at its existing locked 8.0.16 using an override.
Audit thresholds and application interfaces remain unchanged.

- [x] Extend dependency contract fixtures for the approved versions and assert every locked copy of Next.js, sharp, Vitest/mocker, and js-yaml avoids the affected versions. Run `python -m pytest -q tests/developer_workflow/test_frontend_dependency_contract.py` and observe failure against the existing vulnerable lockfile.
- [x] Run `scripts/worktree-deps.ps1 -Mode Status`, verify the shared junction points to the main workspace, then run `-Mode Detach`. Update only the approved manifest entries with apply_patch and regenerate the lockfile with `npm exec --yes --package=npm@10.9.2 -- npm install --package-lock-only --ignore-scripts --no-audit --no-fund`.
- [x] Install fresh isolated dependencies with `npm exec --yes --package=npm@10.9.2 -- npm ci --no-audit --no-fund`; verify `npm ls --depth=0 --json`, `npm audit --omit=dev --audit-level=high`, and `npm audit --audit-level=high` all exit 0. Inspect the lockfile diff for unrelated upgrades and rerun the dependency contracts.
- [x] Run the full `scripts/verify-before-commit.ps1` with formatting, lint, tests and build; run `npm run test:e2e -- --workers=1` with CI=true. Obtain independent review, fix material findings, and commit explicitly scoped files with normal hooks.
- [x] Fast-forward the release branch, refresh its installed dependencies only after checking other shared consumers, run integration regressions, push without force, and verify both push/PR CI runs for the final SHA. Close this plan and regenerate its index only when all acceptance gates are satisfied.

### Security addendum evidence

The new lock contracts first failed in 8 cases against the old dependency
versions, then all 9 passed after the update. npm 10.9.2 initially crashed in
Arborist peer resolution (`edgesOut`) while considering newer Vite/devtools
peers. Pinning the existing Vite 8.0.16 avoided that expansion and allowed the
same package-manager command to succeed without force or legacy-peer flags.
The lockfile changes remain in the selected Next/ESLint, sharp, Vitest/Vite
dependency paths, including compatible updates within existing ranges. The nested
optional @napi-rs/wasm-runtime moved from 1.1.5 to 1.2.3 within its existing
^1.1.4 range, with @tybys/wasm-util 0.10.3 beneath it. No unrelated direct
dependency changed. Fresh isolated npm ci added 626 packages and exited 0.
npm ls and both production/full audits exited 0 with zero vulnerabilities.
The installer reported an EPERM cleanup warning for an optional WASM subtree;
no permission change or forced deletion was attempted.

Next.js 16.3.4 generated frontend AGENTS.md and CLAUDE.md during the browser
test's development-server startup. Their source and markers matched the
installed `next/dist/server/lib/generate-agent-files.js`. These generated
instruction files were removed after testing and are not part of this security
change; `next dev` may regenerate them when it detects a coding agent. The
repository's existing root instructions remain unchanged.

The initial code commits are `8764f7c` and `04d002d`; both are integrated and
pushed. Main-workspace regressions passed 150 backend and 44 frontend tests.
The PR run [34373614201](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34373614201)
and push run [34373609078](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34373609078)
failed on production dependency audit, not application tests. A fresh local
audit also reports five affected package entries (one critical, two high,
two moderate); the earlier zero-audit observation is historical, not current.
References: [Next.js](https://github.com/advisories/GHSA-p293-qw3h-jr36),
[AVIF](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4),
[sharp](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c),
[Vitest](https://github.com/advisories/GHSA-82fw-gwwq-j7x9), and
[js-yaml](https://github.com/advisories/GHSA-2883-xcg3-v3hh).

## Prior Execution Record

Design approved on 2026-09-08. Baseline is `8dd218d`; worktree is clean and frontend dependencies are shared. Prior full baseline evidence: backend 1566 passed / 6 skipped and frontend 377 passed, lint/build passed. Documentation-only plan preparation uses index/lifecycle and formatting checks; full implementation verification is performed per batch.

Ruling: Poll controllers belong to hook lifetime, and cleanup means unmount cleanup. This reconciles the spec's cleanup wording with its explicit requirement that new batches/callback changes preserve the same in-flight request.

Implementation checkpoint (2026-09-09): all six fixes are implemented locally. Batch 1 independent review found no Critical/Important issue; the suggested cached-session revocation test was added. SMTP privacy tests cover the actual transport logger as well as the reset service. Focused backend/CI checks passed (111 tests), broader auth/deployment checks passed (145 tests), and focused frontend checks passed (50 tests). Full validation and release integration remain pending.

Ruling: Finish both batches' code before the complete repository verification, then create separate scoped commits from the same verified working tree. This preserves independently reviewable commits while avoiding a repeated full backend run over unchanged authentication code.

Environment note: Windows PowerShell's staged verifier resolved two Node executables as an array. The commit command removes only the bundled secondary Node directory from its process-local PATH and uses the existing `F:\node.exe`; no hook is bypassed and no persistent environment setting is changed.

Validation follow-up (2026-09-09): the new delayed-AI regression increased the existing workspace suite from 23 to 24 cases. Its split guard now names the new case and retains the exact count. Full TypeScript checking also exposed two pre-existing test fixture errors: the auth-brand query now declares its HTMLElement type, and chat scope uses the actual `folderIds` field rather than the API payload's `folder_ids`. No production behavior or check threshold changed. `python -m pytest -q tests/frontend_structure` passed 82 tests; `node node_modules/typescript/bin/tsc --noEmit --incremental false` passed; targeted AuthPage, chat knowledge context, and workspace AI Vitest tests passed 19 tests. The complete verifier is being rerun with durable output in the ignored `.pytest_cache/pr7-final-verification.log` file.

Validation checkpoint: frontend verification passed all 410 tests, lint, Prettier, and production build; Playwright passed all 3 desktop/mobile/reset-flow cases. The first durable full backend run completed with 1586 passed, 6 skipped, and one Windows test-harness failure: the parent had exited but a zero-time poll observed the child before its exit signal. The test now waits on each process handle with a bounded wait, while retaining the original overall 20/10-second limits after the waits. Both timeout/malformed-host cases passed after the change (2 passed, 42 deselected). A fresh complete verifier is running; this checkpoint does not claim the failed full run passed.

Final local verification (2026-09-09): `scripts/verify-before-commit.ps1` exited 0 with 1587 backend tests passed, 6 skipped, 2 existing httpx deprecation warnings, and all 410 frontend tests passed. Black, Prettier, lint, production build, and whitespace checks passed. The complete output is in `.pytest_cache/pr7-final-verification-retry.log`. `npm run test:e2e -- --workers=1` with `CI=true` passed all 3 cases. Independent batch, integration, and validation-fix reviews found no remaining Critical/Important issue. Batch 1 was committed normally as `8764f7c`; its repository pre-commit hook passed.

Dependency evidence: a fresh isolated temporary npm 10.9.2 installation added 627 packages; `npm ls --depth=0 --json`, production audit, and full audit exited 0, with zero vulnerabilities. Installation emitted a cleanup EPERM warning for a nested optional dependency, but installation and subsequent tree/audit checks succeeded. The diagnostic directory was preserved and the shared worktree dependency junction was not modified by installation.

Security-batch local completion: the full `scripts/verify-before-commit.ps1 -Format` passed with 1592 backend tests passed, 6 skipped, 2 existing httpx deprecation warnings, and 410 frontend tests passed. Formatting, lint, TypeScript and production build passed. Playwright passed 3 tests. Independent dependency review had no Critical/Important findings; its minor documentation correction was applied. Before commit, 14 dependency/lifecycle tests passed and fresh production/full audits again reported zero vulnerabilities. Full verification output is retained in `.pytest_cache/pr7-security-verification.log`. Integration and exact-SHA CI acceptance remain pending.

## Completion Record (2026-09-10)

All six original findings and the approved dependency addendum are integrated
into `release/video-security-integration-20260729`. Implementation commits are
`8764f7c`, `04d002d`, and `af8e132`. For exact code SHA
`af8e1320ad68684eb55f38b595cda7659da94950`, both the
[PR run 34447589542](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34447589542)
and [push run 34447583403](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34447583403)
passed Changes, Backend, Frontend, and CI Success. Main-workspace installation
with npm 10.9.2, the dependency tree, both zero-vulnerability audits, and all
410 frontend tests passed; 14 dependency/lifecycle tests passed after integration.
The existing optional-WASM cleanup warning did not change these successful
exit codes. No permissions were changed and no hook or audit gate was bypassed.

The final plan/index closeout is documentation-only; its own exact-SHA CI is
checked after pushing. PR 7 remains open and ready, with no merge into main,
image publication, production deployment, or live Nginx change. Full local
verification logs were copied to the main workspace's ignored
`.pytest_cache/pr7-evidence-04d002d/` directory before worktree cleanup.
