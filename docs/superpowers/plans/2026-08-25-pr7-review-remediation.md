# PR 7 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned

**Goal:** Fix the authentication, CI-routing, and import-refresh blockers found during the final review of pull request 7.

**Architecture:** Password-reset codes use a database uniqueness boundary plus atomic conditional mutations. CI classification explicitly recognizes backend dependency and plan-policy inputs. Import polling emits one content-ready signal per completed batch, and the shared refresh version reloads statistics and scope options without resetting chat.

**Tech Stack:** FastAPI, SQLAlchemy asyncio, SQLite, pytest, Next.js 16, React, TypeScript, Vitest, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-25-pr7-review-remediation-design.md`

## Global Constraints

- Preserve a generic production response for unknown, inactive, duplicate, and accepted password-reset send requests.
- Enforce reset-code uniqueness and attempt limits in the database, not with a process-local lock.
- Keep password update, code consumption, and session revocation transactionally consistent.
- Keep unknown CI paths fail-closed to backend and frontend jobs.
- Refresh imported content without resetting the active conversation.
- Treat `completed`, `failed`, and `interrupted` as terminal import states.
- Do not merge pull request 7 into `main` or deploy production in this plan.

---

### Task 1: Make Password-Reset Sending Non-Disclosing And Recoverable

**Files:**

- Modify: `app/models.py`
- Modify: `app/services/sqlite_legacy_schema.py`
- Modify: `app/services/system_auth_password_reset.py`
- Modify: `app/services/email.py`
- Modify: `tests/system_auth/test_password_reset.py`
- Create: `tests/test_sqlite_password_reset_migration.py`

**Interfaces:**

- Consumes: `send_password_reset_code(db, email, client_ip, debug)` and SQLite startup migration hooks.
- Produces: one reset-code row per email, generic duplicate-send responses, rollback after SMTP failure, and reset-specific mail copy.

- [x] **Step 1: Write failing endpoint and migration tests**

Add tests proving duplicate and unknown sends have the same status/message,
parallel sends leave one row, SMTP failure removes the reserved row and permits
retry, reset email copy does not mention registration, and a legacy duplicate
table is deduplicated before its unique index is created.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m pytest -q tests/system_auth/test_password_reset.py tests/test_sqlite_password_reset_migration.py
```

Expected: the new assertions fail because duplicate sends return 429, failed
mail leaves a row, reset copy uses registration wording, and email uniqueness
is absent.

- [x] **Step 3: Implement the minimal send and schema changes**

Declare a unique email constraint, add an idempotent SQLite migration that
keeps the newest duplicate row, catch only the insert uniqueness race, return
the generic response for a live row, delete the exact reservation after mail
failure, and add an explicit reset email purpose/template.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command and require every test to pass.

- [x] **Step 5: Commit Batch 1 sending changes**

```powershell
git add app/models.py app/services/sqlite_legacy_schema.py app/services/system_auth_password_reset.py app/services/email.py tests/system_auth/test_password_reset.py tests/test_sqlite_password_reset_migration.py
git commit -m "fix: harden password reset delivery"
```

### Task 2: Consume Reset Codes And Count Attempts Atomically

**Files:**

- Modify: `app/services/system_auth_password_reset.py`
- Modify: `tests/system_auth/test_password_reset.py`

**Interfaces:**

- Consumes: a unique `PasswordResetCode.email`, `MAX_ATTEMPTS`, and the submitted code hash.
- Produces: atomic invalid-attempt increments and single-use successful consumption.

- [ ] **Step 1: Write failing concurrency tests**

Add tests that run parallel invalid confirmations and assert the row is removed
at the configured attempt limit, then run parallel valid confirmations and
assert exactly one succeeds.

- [ ] **Step 2: Run the concurrency tests and verify RED**

```powershell
python -m pytest -q tests/system_auth/test_password_reset.py -k "parallel or atomic"
```

Expected: lost increments or multiple successful confirmations expose the
current read-modify-write behavior.

- [ ] **Step 3: Implement atomic invalid update and valid consumption**

Use conditional SQL `UPDATE ... attempts = attempts + 1 RETURNING attempts`
for an incorrect live code and conditional `DELETE ... RETURNING` for a correct
live code. Delete a row that reaches `MAX_ATTEMPTS`; update the password and
revoke sessions only after successful consumption.

- [ ] **Step 4: Run password-reset regressions and verify GREEN**

```powershell
python -m pytest -q tests/system_auth/test_password_reset.py
```

- [ ] **Step 5: Commit Batch 1 atomic confirmation**

```powershell
git add app/services/system_auth_password_reset.py tests/system_auth/test_password_reset.py
git commit -m "fix: consume password reset codes atomically"
```

### Task 3: Route Dependency And Plan Policy Inputs Through CI

**Files:**

- Modify: `scripts/classify-ci-paths.py`
- Modify: `tests/developer_workflow/test_ci_paths.py`

**Interfaces:**

- Consumes: repository-relative changed paths.
- Produces: `backend=true`, `frontend=false`, and `docs_only=false` for `requirements-dev.txt` and plan lifecycle inputs.

- [ ] **Step 1: Add failing exact-path classifier cases**

Cover `requirements-dev.txt`, a dated file in `docs/superpowers/plans/`, and
`docs/superpowers/plans/README.md`. Assert each schedules backend policy tests
and is not docs-only.

- [ ] **Step 2: Run classifier tests and verify RED**

```powershell
python -m pytest -q tests/developer_workflow/test_ci_paths.py
```

- [ ] **Step 3: Add minimal backend dependency and policy path rules**

Introduce focused backend-only exact/prefix collections before the generic
documentation suffix branch. Do not broaden all documentation to full CI.

- [ ] **Step 4: Run classifier tests and verify GREEN**

Run the Step 2 command and require every test to pass.

- [ ] **Step 5: Commit Batch 2 CI routing**

```powershell
git add scripts/classify-ci-paths.py tests/developer_workflow/test_ci_paths.py
git commit -m "ci: route dependency and plan policy changes"
```

### Task 4: Refresh Imported Content At Terminal Task State

**Files:**

- Modify: `frontend/components/import-modal/useImportModal.ts`
- Modify: `frontend/components/ImportModal.test.tsx`
- Modify: `frontend/components/chat/useChatKnowledgeContext.ts`
- Modify: `frontend/components/ChatPanel.test.tsx`

**Interfaces:**

- Consumes: `ImportTaskStatus.status`, `onImported`, and the existing `kb-stats` refresh version.
- Produces: one `onImported()` call for each terminal batch containing a completed task; `failed` and `interrupted` stop polling; scope options reload on `statsKey` without chat reset.

- [ ] **Step 1: Write failing polling and refresh tests**

Test pending to completed notification, multi-part single notification,
interrupted terminal behavior, no notification for an all-failed batch, and a
`statsKey` change that reloads stats and scope options without invoking reset
actions.

- [ ] **Step 2: Run focused frontend tests and verify RED**

```powershell
$env:VITEST_MAX_THREADS='4'
$env:VITEST_MIN_THREADS='1'
npm test -- components/ImportModal.test.tsx components/ChatPanel.test.tsx
```

- [ ] **Step 3: Implement terminal batch notification and context refresh**

Remove submission-time `onImported` calls, model terminal states explicitly,
track the notified task-set signature, and emit after polling observes a
terminal batch with a completion. Split scope loading from knowledge-base reset
so `statsKey` reloads data without clearing chat state.

- [ ] **Step 4: Run focused frontend tests and verify GREEN**

Run the Step 2 command and require every test to pass.

- [ ] **Step 5: Commit Batch 2 frontend consistency**

```powershell
git add frontend/components/import-modal/useImportModal.ts frontend/components/ImportModal.test.tsx frontend/components/chat/useChatKnowledgeContext.ts frontend/components/ChatPanel.test.tsx
git commit -m "fix: refresh completed imports consistently"
```

### Task 5: Verify, Review, Integrate, And Ready Pull Request 7

**Files:**

- Modify: `docs/superpowers/plans/2026-08-25-pr7-review-remediation.md`
- Modify: `docs/superpowers/plans/README.md`

**Interfaces:**

- Consumes: Tasks 1-4, repository verification scripts, GitHub CI, and pull request 7.
- Produces: a completed plan, fast-forwarded release branch, current PR description, and Ready status only after all gates pass.

- [ ] **Step 1: Run focused integrated checks**

```powershell
python -m pytest -q tests/system_auth/test_password_reset.py tests/test_sqlite_password_reset_migration.py tests/developer_workflow/test_ci_paths.py tests/developer_workflow/test_plan_lifecycle.py
python scripts/generate-plan-index.py --check
```

Run the two focused frontend files from Task 4 and require success.

- [ ] **Step 2: Run complete local verification and audits**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1 -Format -SkipBackendTests
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-before-commit.ps1
npm audit --omit=dev --audit-level=high
npm audit --audit-level=high
```

The two high-severity audits must exit zero. Record any lower-severity advisory
accurately rather than describing the full tree as vulnerability-free.

- [ ] **Step 3: Request a fresh code review**

Review the complete remediation range. Fix every Critical or Important finding
and repeat focused plus complete verification after any production change.

- [ ] **Step 4: Close the plan and integrate the worktree**

Set the status to `completed`, check every step, record exact verification
results, regenerate the plan index, commit the closure, and fast-forward
`fix/pr7-review-blockers` into
`release/video-security-integration-20260729` only while both checkouts are
clean.

- [ ] **Step 5: Push and wait for both remote CI events**

Push without force. Require successful `Changes`, `Backend`, `Frontend`, and
`CI Success` jobs for both the push and pull-request runs at the final SHA.

- [ ] **Step 6: Update PR facts and mark Ready**

Replace stale commit/test/audit statements in pull request 7 with the final
evidence. Mark it Ready only after Step 5 succeeds and no Critical or Important
review findings remain. Do not merge it into `main`.
