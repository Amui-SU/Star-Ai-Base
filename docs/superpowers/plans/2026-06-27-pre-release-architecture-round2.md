# Pre-release Architecture Maintenance Round 2 Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue pre-release maintenance by shrinking global frontend style ownership and adding structure guards, without changing product behavior or starting learning-review/import-source feature work.

**Architecture:** Keep selectors and rendered markup unchanged. Move cohesive CSS groups from `globals.css` into imported feature stylesheets, then verify with structure tests, existing layout tests, component tests, lint, and build.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, pytest structure tests.

---

### Task 1: Split Workspace And Account Shell Styles

**Files:**

- Create: `frontend/app/styles/workspace.css`
- Create: `frontend/app/styles/account-panels.css`
- Modify: `frontend/app/globals.css`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/app/page.test.tsx`, `frontend/components/UserMenu.test.tsx`, `frontend/components/ApiAccountsPanel.test.tsx`

- [x] **Step 1: Write failing structure tests**

Add assertions that `globals.css` imports `workspace.css` and `account-panels.css`, and no longer owns `.workspace-card`, `.workspace-topbar`, `.user-menu`, `.admin-users-panel`, or `.api-accounts-layout`.

Run: `python -m pytest tests/test_frontend_structure.py -q -k "workspace_styles or account_panel_styles"`

Expected: FAIL because the styles are still inline in `globals.css`.

- [x] **Step 2: Move selectors without renaming**

Move the matching selectors into the new stylesheet files and add imports near the top of `globals.css`.

- [x] **Step 3: Verify behavior**

Run:

- `cd frontend; npm test -- page.test.tsx UserMenu.test.tsx ApiAccountsPanel.test.tsx`

Expected: PASS.

### Task 2: Split Sources And Knowledge Sidebar Styles

**Files:**

- Create: `frontend/app/styles/sources.css`
- Create: `frontend/app/styles/knowledge-sidebar.css`
- Modify: `frontend/app/globals.css`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/components/SourcesPanel.test.tsx`, `frontend/app/mobile-chat-layout.test.ts`, `frontend/app/source-status-theme.test.ts`

- [x] **Step 1: Write failing structure tests**

Add assertions that `globals.css` imports `sources.css` and `knowledge-sidebar.css`, and no longer owns `.sources-panel-head`, `.folder-card`, `.video-card`, `.video-player-modal`, or `.knowledge-panel`.

Run: `python -m pytest tests/test_frontend_structure.py -q -k "sources_styles or knowledge_sidebar_styles"`

Expected: FAIL because those selectors are still inline in `globals.css`.

- [x] **Step 2: Move selectors without renaming**

Move sources/folder/video/player styles into `sources.css` and knowledge sidebar styles into `knowledge-sidebar.css`.

- [x] **Step 3: Verify behavior**

Run:

- `cd frontend; npm test -- SourcesPanel.test.tsx mobile-chat-layout.test.ts source-status-theme.test.ts`

Expected: PASS.

### Task 3: Full Verification And Merge

**Files:**

- Modify: `docs/大版本完善执行方案.md`

- [x] **Step 1: Update maintenance record**

Record the round 2 architecture-only CSS split, including the verification commands.

- [x] **Step 2: Run repository verification**

Run:

- `git status --short`
- `git diff --check`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1`

Expected: backend tests, frontend lint, frontend tests, and build all pass.

- [x] **Step 3: Commit and fast-forward merge**

Stage only source, test, and doc changes. Commit on `maintenance/pre-release-architecture-round2`, fast-forward merge into `main`, and run final targeted checks on `main`.
