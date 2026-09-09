# PR 7 Adversarial Remediation Implementation Plan

**Status:** partial

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
- [ ] Commit batch 2 with normal hooks; fresh dependency installation in an isolated temporary directory uses npm 10.9.2 and verifies tree/audits without touching shared dependencies.
- [ ] Integrate and push the release branch; validate push and PR workflows for final SHA. Update plan status/checklist and regenerate index using `python scripts/generate-plan-index.py` when the behavior is integrated.

## Execution Record

Design approved on 2026-09-08. Baseline is `8dd218d`; worktree is clean and frontend dependencies are shared. Prior full baseline evidence: backend 1566 passed / 6 skipped and frontend 377 passed, lint/build passed. Documentation-only plan preparation uses index/lifecycle and formatting checks; full implementation verification is performed per batch.

Ruling: Poll controllers belong to hook lifetime, and cleanup means unmount cleanup. This reconciles the spec's cleanup wording with its explicit requirement that new batches/callback changes preserve the same in-flight request.

Implementation checkpoint (2026-09-09): all six fixes are implemented locally. Batch 1 independent review found no Critical/Important issue; the suggested cached-session revocation test was added. SMTP privacy tests cover the actual transport logger as well as the reset service. Focused backend/CI checks passed (111 tests), broader auth/deployment checks passed (145 tests), and focused frontend checks passed (50 tests). Full validation and release integration remain pending.

Ruling: Finish both batches' code before the complete repository verification, then create separate scoped commits from the same verified working tree. This preserves independently reviewable commits while avoiding a repeated full backend run over unchanged authentication code.

Environment note: Windows PowerShell's staged verifier resolved two Node executables as an array. The commit command removes only the bundled secondary Node directory from its process-local PATH and uses the existing `F:\node.exe`; no hook is bypassed and no persistent environment setting is changed.

Validation follow-up (2026-09-09): the new delayed-AI regression increased the existing workspace suite from 23 to 24 cases. Its split guard now names the new case and retains the exact count. Full TypeScript checking also exposed two pre-existing test fixture errors: the auth-brand query now declares its HTMLElement type, and chat scope uses the actual `folderIds` field rather than the API payload's `folder_ids`. No production behavior or check threshold changed. `python -m pytest -q tests/frontend_structure` passed 82 tests; `node node_modules/typescript/bin/tsc --noEmit --incremental false` passed; targeted AuthPage, chat knowledge context, and workspace AI Vitest tests passed 19 tests. The complete verifier is being rerun with durable output in the ignored `.pytest_cache/pr7-final-verification.log` file.

Validation checkpoint: frontend verification passed all 410 tests, lint, Prettier, and production build; Playwright passed all 3 desktop/mobile/reset-flow cases. The first durable full backend run completed with 1586 passed, 6 skipped, and one Windows test-harness failure: the parent had exited but a zero-time poll observed the child before its exit signal. The test now waits on each process handle with a bounded wait, while retaining the original overall 20/10-second limits after the waits. Both timeout/malformed-host cases passed after the change (2 passed, 42 deselected). A fresh complete verifier is running; this checkpoint does not claim the failed full run passed.

Final local verification (2026-09-09): `scripts/verify-before-commit.ps1` exited 0 with 1587 backend tests passed, 6 skipped, 2 existing httpx deprecation warnings, and all 410 frontend tests passed. Black, Prettier, lint, production build, and whitespace checks passed. The complete output is in `.pytest_cache/pr7-final-verification-retry.log`. `npm run test:e2e -- --workers=1` with `CI=true` passed all 3 cases. Independent batch, integration, and validation-fix reviews found no remaining Critical/Important issue. Batch 1 was committed normally as `8764f7c`; its repository pre-commit hook passed.

Dependency evidence: a fresh isolated temporary npm 10.9.2 installation added 627 packages; `npm ls --depth=0 --json`, production audit, and full audit exited 0, with zero vulnerabilities. Installation emitted a cleanup EPERM warning for a nested optional dependency, but installation and subsequent tree/audit checks succeeded. The diagnostic directory was preserved and the shared worktree dependency junction was not modified by installation.
