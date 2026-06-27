# Medium Low Risk Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the current medium/low priority maintenance risks in the isolated worktree without changing product behavior.

**Architecture:** Keep the public component APIs stable and move self-contained UI/state responsibilities into focused files. Use structure tests to lock the new boundaries and existing Vitest coverage to catch behavior regressions.

**Tech Stack:** Next.js client components, React hooks, Vitest, React Testing Library, pytest structure tests.

---

### Task 1: Extract Auth Demo Preview

**Files:**

- Create: `frontend/components/auth/useAuthDemoPreview.ts`
- Create: `frontend/components/auth/AuthDemoPreview.tsx`
- Modify: `frontend/components/AuthPage.tsx`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/components/AuthPage.test.tsx`

- [x] **Step 1: Write the failing structure test**

Add a test that asserts `AuthPage.tsx` imports the auth demo component/hook and no longer owns the demo animation constants.

Run: `python -m pytest tests/test_frontend_structure.py -q -k auth_demo`

Expected: FAIL because the files and imports do not exist yet.

- [x] **Step 2: Extract the hook and component**

Move `DemoStep`, demo question/answer/source data, typing timers, and replay timers from `AuthPage.tsx` into `useAuthDemoPreview.ts`; move the right-side visual JSX into `AuthDemoPreview.tsx`.

- [x] **Step 3: Replace inline AuthPage demo JSX**

Render `<AuthDemoPreview visible={visible} />` in the existing right-side section and keep the current classes/text unchanged.

- [x] **Step 4: Verify auth tests**

Run: `cd frontend; npm test -- AuthPage.test.tsx`

Expected: PASS.

### Task 2: Extract Sources Video Player Portal

**Files:**

- Create: `frontend/components/sources/VideoPlayerPortal.tsx`
- Modify: `frontend/components/SourcesPanel.tsx`
- Modify: `frontend/components/SourcesPanel.test.tsx`
- Modify: `tests/test_frontend_structure.py`

- [x] **Step 1: Write the failing boundary test**

Add a structure test that asserts `SourcesPanel.tsx` imports `VideoPlayerPortal`, and no longer imports `createPortal` or contains the Bilibili iframe URL.

Run: `python -m pytest tests/test_frontend_structure.py -q -k sources_video_player`

Expected: FAIL because the portal is still inline.

- [x] **Step 2: Add a playback behavior test**

In `SourcesPanel.test.tsx`, open a folder, click the play button, and assert the iframe appears with the video title. This test may already pass before extraction; it protects the behavior through the refactor.

- [x] **Step 3: Extract the portal**

Move the modal/iframe JSX and `createPortal` import into `VideoPlayerPortal.tsx`. Pass `video` and `onClose` props from `SourcesPanel`.

- [x] **Step 4: Verify sources tests**

Run: `cd frontend; npm test -- SourcesPanel.test.tsx`

Expected: PASS.

### Task 3: Extract Workspace State Hook

**Files:**

- Create: `frontend/app/useWorkspaceState.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/app/page.test.tsx`

- [x] **Step 1: Write the failing structure test**

Add a structure test that asserts `page.tsx` imports `useWorkspaceState`, the hook file exists, and the page no longer defines `getInitialSidebarOpen` or `isMobileViewport`.

Run: `python -m pytest tests/test_frontend_structure.py -q -k workspace_state`

Expected: FAIL because the hook does not exist yet.

- [x] **Step 2: Extract state and callbacks**

Move sidebar sizing/open state, sidebar mode, conversation request state, and related callbacks into `useWorkspaceState.ts`. Keep the exported `SidebarMode` type and helper return shape explicit.

- [x] **Step 3: Wire page to the hook**

Use the hook return values in `page.tsx` while leaving rendered markup and child props unchanged.

- [x] **Step 4: Verify page tests**

Run: `cd frontend; npm test -- page.test.tsx`

Expected: PASS.

### Task 4: Document And Verify

**Files:**

- Modify: `docs/大版本完善执行方案.md`

- [x] **Step 1: Update the risk log**

Add a 2026-06-27 worktree note for the three refactors and the tests that protect them.

- [x] **Step 2: Run targeted checks**

Run:

- `python -m pytest tests/test_frontend_structure.py -q`
- `cd frontend; npm test -- AuthPage.test.tsx SourcesPanel.test.tsx page.test.tsx`

Expected: PASS.

- [x] **Step 3: Run full verification before commit**

Run:

- `git status --short`
- `git diff --check`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1`

Expected: backend, frontend lint, frontend tests, and build all pass.
