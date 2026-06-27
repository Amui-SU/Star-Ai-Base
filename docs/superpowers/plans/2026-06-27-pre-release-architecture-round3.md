# Pre-release Architecture Maintenance Round 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the next safe slice of `globals.css` decomposition before feature work resumes, without changing chat, import, or organize behavior.

**Architecture:** Keep all selectors, markup, and component APIs stable. Move cohesive chat/composer and import/organize CSS groups into imported feature stylesheets, then verify with structure tests and the existing component/layout tests that read the fully expanded stylesheet.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, pytest structure tests.

---

### Task 1: Split Chat And Composer Styles

**Files:**

- Create: `frontend/app/styles/chat.css`
- Create: `frontend/app/styles/chat-controls.css`
- Modify: `frontend/app/globals.css`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/components/ChatPanel.test.tsx`, `frontend/app/mobile-chat-layout.test.ts`, `frontend/app/source-status-theme.test.ts`

- [x] **Step 1: Write failing structure tests**

Add assertions that `globals.css` imports `chat.css` and `chat-controls.css`, and no longer owns `.message`, `.markdown`, `.web-search-live-status`, `.composer-shell`, `.scope-picker`, or `.model-status-card`.

Run: `python -m pytest tests/test_frontend_structure.py -q -k "chat_styles or chat_control_styles"`

Expected: FAIL because the styles are still inline in `globals.css`.

- [x] **Step 2: Move selectors without renaming**

Move chat message, markdown, thinking/source/web-search display, empty state, prompt, composer, scope picker, model selector, input, button, and send/status controls into the two new stylesheet files.

- [x] **Step 3: Verify behavior**

Run:

- `cd frontend; npm test -- ChatPanel.test.tsx mobile-chat-layout.test.ts source-status-theme.test.ts`

Expected: PASS.

### Task 2: Split Import And Organize Styles

**Files:**

- Create: `frontend/app/styles/import-organize.css`
- Modify: `frontend/app/globals.css`
- Modify: `tests/test_frontend_structure.py`
- Verify: `frontend/components/ImportModal.test.tsx`, `frontend/app/mobile-chat-layout.test.ts`

- [x] **Step 1: Write failing structure tests**

Add assertions that `globals.css` imports `import-organize.css`, and no longer owns `.import-modal`, `.import-method-card`, `.import-local-video-card`, `.organize-modal`, or `.organize-item`.

Run: `python -m pytest tests/test_frontend_structure.py -q -k import_organize_styles`

Expected: FAIL because those selectors are still inline in `globals.css`.

- [x] **Step 2: Move selectors without renaming**

Move import modal and organize preview modal selectors into `import-organize.css`.

- [x] **Step 3: Verify behavior**

Run:

- `cd frontend; npm test -- ImportModal.test.tsx mobile-chat-layout.test.ts`

Expected: PASS.

### Task 3: Full Verification And Merge

**Files:**

- Modify: `docs/大版本完善执行方案.md`

- [x] **Step 1: Update maintenance record**

Record the round 3 architecture-only CSS split and the verification commands.

- [x] **Step 2: Run repository verification**

Run:

- `git status --short`
- `git diff --check`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1`

Expected: backend tests, frontend lint, frontend tests, and build all pass.

- [ ] **Step 3: Commit and fast-forward merge**

Stage only source, test, and doc changes. Commit on `maintenance/pre-release-architecture-round3`, fast-forward merge into `main`, and run final targeted checks on `main`.
