# Four Issues Closeout Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four remaining pre-release maintenance issues without changing product behavior.

**Architecture:** Keep runtime behavior stable while moving ingestion task updates into the service layer, strengthening legacy-router boundaries, splitting a large test tail into a focused file, and correcting stale release-maintenance documentation. The routers should orchestrate requests, while `app/services/ingestion_tasks.py` owns task persistence and status mutation.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, pytest, Vitest/Next.js verification through the repository pre-commit script.

---

### Task 1: Ingestion Task Lifecycle Boundary

**Files:**

- Modify: `app/services/ingestion_tasks.py`
- Modify: `app/routers/imports.py`
- Modify: `app/routers/knowledge_bases.py`
- Test: `tests/test_ingestion_tasks.py`
- Test: `tests/test_service_boundaries.py`

- [x] **Step 1: Write failing tests**

Add tests that require `update_ingestion_task` in `app/services/ingestion_tasks.py`, require routers to import it, and forbid router-local `_update_import_task` / `_update_task` helpers.

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/test_ingestion_tasks.py tests/test_service_boundaries.py -q`
Expected: FAIL because `update_ingestion_task` does not exist and router-local task update helpers still exist.

- [x] **Step 3: Implement service update helper**

Add `update_ingestion_task(task_id, **fields)` that opens `get_db_context`, applies fields to an existing task, commits, and returns `True` when updated.

- [x] **Step 4: Route callers through the service**

Replace import/local video and scoped build task mutation helpers with `update_ingestion_task`.

- [x] **Step 5: Verify green**

Run: `python -m pytest tests/test_ingestion_tasks.py tests/test_service_boundaries.py tests/test_imports.py -q`
Expected: PASS.

### Task 2: Legacy Boundary And Large Test Split

**Files:**

- Modify: `tests/test_folder_ingestion.py`
- Modify: `tests/test_knowledge_base_scoping.py`
- Test: `tests/test_service_boundaries.py`

- [x] **Step 1: Write failing structure test**

Add a service-boundary assertion that scoped build/sync tests import `sync_folder` from `app.services.folder_ingestion`, not from `app.routers.knowledge`.

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/test_service_boundaries.py -q`
Expected: FAIL because the large scoping test file still imports `_sync_folder` from the legacy router.

- [x] **Step 3: Split focused build/sync tests**

Move folder-sync tail tests from `tests/test_knowledge_base_scoping.py` into `tests/test_folder_ingestion.py`, and update the tests to use `app.services.folder_ingestion.sync_folder`.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/test_service_boundaries.py tests/test_folder_ingestion.py tests/test_knowledge_base_scoping.py -q`
Expected: PASS.

### Task 3: Documentation Drift Closeout

**Files:**

- Modify: `README.md`
- Modify: `docs/大版本完善执行方案.md`
- Modify: `docs/功能大纲.md`
- Modify: `frontend/APK-打包说明.md`
- Test: `tests/test_docker_support.py` or `tests/test_service_boundaries.py`

- [x] **Step 1: Add doc guard**

Add assertions that the maintenance report no longer claims `globals.css` still owns demo/local/glass styles, documents interrupted-only task recovery clearly, and references the production gateway limit in mobile/APK docs.

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/test_docker_support.py tests/test_service_boundaries.py -q`
Expected: FAIL on stale docs.

- [x] **Step 3: Update docs**

Correct the stale `globals.css` note, clarify CORS wording, clarify legacy helper status, and align APK production guidance with gateway rate-limit docs.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/test_docker_support.py tests/test_service_boundaries.py -q`
Expected: PASS.

### Task 4: Full Commit Verification

**Files:**

- All changed files.

- [x] **Step 1: Run repository commit checks**

Run the exact `AGENTS.md` flow: status, `git diff --check`, format script, full verification script, explicit staging, cached checks, commit, final status.

- [x] **Step 2: Merge back and cleanup**

Merge `maintenance/four-issues-closeout` into `main`, run targeted post-merge verification, and remove the temporary worktree/branch when clean.
