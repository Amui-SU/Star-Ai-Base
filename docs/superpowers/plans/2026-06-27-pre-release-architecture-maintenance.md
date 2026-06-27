# Pre-release Architecture Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce pre-release architecture and maintainability risk without adding learning-review, import-source, or other product features.

**Architecture:** Keep runtime behavior unchanged and move isolated responsibilities out of large files behind structure tests and existing behavior tests. Prefer pure helper extraction and router/service boundaries before larger UI or task-queue changes.

**Tech Stack:** FastAPI, SQLAlchemy async, Next.js 16, React 19, TypeScript, Vitest, pytest structure tests.

---

### Task 1: Extract SourcesPanel Pure Logic

**Files:**

- Create: `frontend/components/sources/sourcesPanelLogic.ts`
- Create: `frontend/components/sources/sourcesPanelLogic.test.ts`
- Modify: `frontend/components/SourcesPanel.tsx`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/components/SourcesPanel.test.tsx`

- [x] **Step 1: Write the failing structure test**

Add a test that asserts `SourcesPanel.tsx` imports `sourcesPanelLogic` and no longer owns pure formatting/status/button-label helpers.

Run: `python -m pytest tests/test_frontend_structure.py -q -k sources_panel_logic`

Expected: FAIL because `sourcesPanelLogic.ts` does not exist and helpers are still inline.

- [x] **Step 2: Write pure helper tests**

Create `sourcesPanelLogic.test.ts` with assertions for:

```ts
expect(formatFolderSyncTime("2026-06-27 08:09:00")).toBe("06/27 08:09");
expect(
  getSourcesBuildButtonText({
    building: false,
    selectedCount: 0,
    selectedVideoCount: 0,
    targetKnowledgeBase: "「测试库」",
    selectedFolderIds: [],
    folders: [],
    statusMap: {},
  }),
).toBe("选择收藏夹或视频");
```

Run: `cd frontend; npm test -- sourcesPanelLogic.test.ts`

Expected: FAIL because the module is missing.

- [x] **Step 3: Extract helpers**

Move `formatTime`, `getFolderStatus`, and `getButtonText` into `sourcesPanelLogic.ts` as exported pure functions:

- `formatFolderSyncTime(value?: string): string | null`
- `getSourcesFolderStatus(args): SourcesFolderDisplayStatus`
- `getSourcesBuildButtonText(args): string`

- [x] **Step 4: Wire SourcesPanel to helpers**

Import the helpers in `SourcesPanel.tsx`. Keep rendered text, CSS classes, and API calls unchanged.

- [x] **Step 5: Verify task**

Run:

- `python -m pytest tests/test_frontend_structure.py -q -k sources_panel_logic`
- `cd frontend; npm test -- sourcesPanelLogic.test.ts SourcesPanel.test.tsx`

Expected: PASS.

### Task 2: Split Chat Configuration Boundaries

**Files:**

- Create: `app/services/chat_config.py`
- Modify: `app/routers/chat.py`
- Modify: `tests/test_service_boundaries.py`
- Verify: `tests/test_chat_config_permissions.py`, `tests/test_chat_user_credentials.py`

- [ ] **Step 1: Write the failing boundary test**

Add a service-boundary test that asserts provider metadata, provider env mappings, settings env writes, and web-search normalization are no longer declared in `app/routers/chat.py`.

Run: `python -m pytest tests/test_service_boundaries.py -q -k chat_config`

Expected: FAIL because config helpers are still in the router.

- [ ] **Step 2: Move config helpers into service**

Move only configuration metadata and pure/persistence helpers into `app/services/chat_config.py`. Keep FastAPI route handlers in `chat.py`.

- [ ] **Step 3: Verify route behavior**

Run:

- `python -m pytest tests/test_chat_config_permissions.py tests/test_chat_user_credentials.py -q`
- `python -m pytest tests/test_service_boundaries.py -q -k chat_config`

Expected: PASS.

### Task 3: Add CSS Split Guard Before Moving Styles

**Files:**

- Modify: `tests/test_frontend_structure.py`
- Create later: `frontend/app/styles/*.css`
- Modify later: `frontend/app/globals.css`
- Verify: `frontend/app/api-accounts-layout.test.ts`, `frontend/app/mobile-chat-layout.test.ts`, `frontend/app/source-status-theme.test.ts`

- [ ] **Step 1: Add a structure test for CSS ownership**

Add a test documenting the first CSS split target: auth styles, modal styles, and source/sidebar styles should move under `frontend/app/styles/` before product features resume.

- [ ] **Step 2: Move one CSS section at a time**

Move only one section per commit and keep `globals.css` importing the extracted file.

- [ ] **Step 3: Verify layout tests and full build**

Run:

- `cd frontend; npm test -- api-accounts-layout.test.ts mobile-chat-layout.test.ts source-status-theme.test.ts`
- `cd frontend; npm run build`

Expected: PASS.

### Task 4: Full Verification And Documentation

**Files:**

- Modify: `docs/大版本完善执行方案.md`

- [ ] **Step 1: Update maintenance record**

Record completed architecture-only changes under the 2026-06-27 execution log and explicitly note that learning review/import-source features remain deferred.

- [ ] **Step 2: Run full verification before commit**

Run:

- `git status --short`
- `git diff --check`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1`

Expected: backend tests, frontend lint, frontend tests, and build all pass.
