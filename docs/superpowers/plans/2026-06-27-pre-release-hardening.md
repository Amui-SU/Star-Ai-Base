# Pre-Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the approved pre-release maintenance items 1, 5, and 6 without changing product behavior.

**Architecture:** Keep frontend class names, route paths, response fields, and task behavior stable. Move residual CSS ownership into imported feature stylesheets, extend the existing ingestion task service for task creation/status presentation, and document production verification-code gateway rate limiting with a structure guard.

**Tech Stack:** FastAPI, SQLAlchemy async, Pytest, Next.js, React, Vitest, CSS imports.

---

### Task 1: Final `globals.css` Residual Split

**Files:**

- Modify: `tests/test_frontend_structure.py`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/styles/chat.css`
- Modify: `frontend/app/styles/chat-controls.css`
- Modify: `frontend/app/styles/modals.css`
- Create: `frontend/app/styles/demo.css`

- [ ] **Step 1: Write the failing structure test**

Add assertions that `globals.css` imports `demo.css` and no longer owns `.user-message-actions`, `.empty-hero`, `.kb-subtle-stat`, `.glass-action-btn`, `.demo-modal`, or `@keyframes fadeUp`.

Run: `python -m pytest tests\test_frontend_structure.py -q -k residual`

Expected: FAIL because those selectors still live in `globals.css`.

- [ ] **Step 2: Move CSS without renaming selectors**

Move chat empty state and user-message action rules into `chat.css`, the subtle KB stat into `chat-controls.css`, modal animation/glass action into `modals.css`, and demo-only selectors into `demo.css`. Keep all selectors and declarations unchanged.

- [ ] **Step 3: Verify CSS structure and affected frontend tests**

Run:

- `python -m pytest tests\test_frontend_structure.py -q`
- `cd frontend; npm test -- ChatPanel.test.tsx mobile-chat-layout.test.ts api-accounts-layout.test.ts source-status-theme.test.ts`

Expected: all selected tests pass.

### Task 5: Backend Knowledge/Import Boundary Slimming

**Files:**

- Modify: `tests/test_ingestion_tasks.py`
- Modify: `tests/test_service_boundaries.py`
- Modify: `app/services/ingestion_tasks.py`
- Modify: `app/routers/imports.py`
- Modify: `app/routers/knowledge_bases.py`

- [ ] **Step 1: Write failing service and boundary tests**

Add tests for service-level `create_ingestion_task` and `build_status_payload`, and a structure test asserting import/knowledge-base routers use the ingestion task service instead of owning task creation/status payload mapping.

Run:

- `python -m pytest tests\test_ingestion_tasks.py -q -k "create_ingestion_task or build_status_payload"`
- `python -m pytest tests\test_service_boundaries.py -q -k ingestion`

Expected: FAIL because the helpers and delegation do not exist yet.

- [ ] **Step 2: Extend the ingestion task service**

Implement `create_ingestion_task` and `build_status_payload` in `app/services/ingestion_tasks.py`. Preserve the exact persisted defaults and response keys currently produced by routers.

- [ ] **Step 3: Delegate routers to the service**

Replace local import task creation and build-status response mapping with the service helpers. Keep route validation, background task scheduling, and response model construction unchanged.

- [ ] **Step 4: Verify import/knowledge targeted tests**

Run:

- `python -m pytest tests\test_ingestion_tasks.py tests\test_service_boundaries.py -q`
- `python -m pytest tests\test_imports.py tests\test_knowledge_base_scoping.py -q`

Expected: all selected tests pass.

### Task 6: Production Verification-Code Rate-Limit Defense

**Files:**

- Modify: `tests/test_docker_support.py`
- Modify: `README.md`
- Modify: `docs/移动端发布检查清单.md`
- Modify: `docs/大版本完善执行方案.md`

- [ ] **Step 1: Write the failing documentation guard**

Add a test that checks production deployment docs include a gateway or reverse-proxy rate limit for `POST /system-auth/send-code`, and that the guidance mentions per-IP enforcement and preserving forwarded client IP.

Run: `python -m pytest tests\test_docker_support.py -q -k verification`

Expected: FAIL because only the risk table currently mentions this at a high level.

- [ ] **Step 2: Add deployment hardening guidance**

Document the required production outer rate limit, recommended starting policy, and `X-Forwarded-For`/real client IP requirement. Keep app runtime behavior unchanged.

- [ ] **Step 3: Update the risk table**

Mark the existing verification-code frequency-bypass risk as app-level fixed plus production gateway guard documented.

- [ ] **Step 4: Verify docs guard**

Run: `python -m pytest tests\test_docker_support.py tests\test_readme_links.py -q`

Expected: all selected tests pass.

### Final Verification

- [ ] Run `git status --short`
- [ ] Run `git diff --check`
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format`
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1`
- [ ] Stage only intended files explicitly
- [ ] Run `git diff --cached --check`
- [ ] Run `git diff --cached --name-only`
- [ ] Commit and let hooks run
- [ ] Run `git log -1 --oneline`
- [ ] Run `git status --short`
- [ ] Fast-forward merge back to `main`
