# Video Note Branch Integration Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `agent/video-note-ui-polish` with the latest `main` without losing either branch's video-note, multi-part import, authentication, Playwright, dependency-security, or Python-runtime changes.

**Architecture:** Merge `main` into the existing isolated feature worktree first, resolve each content conflict by preserving compatible behavior from both sides, and validate the combined tree before merging the feature branch back to `main`. Existing focused tests around imports, video-note editing/alignment, runtime selection, CI policy, and browser layout form the behavioral contract.

**Tech Stack:** Git, Python/pytest, Next.js/React/TypeScript, Vitest, Playwright, PowerShell

---

### Task 1: Establish the feature-branch baseline

**Files:**

- Verify: `requirements.txt`
- Verify: `frontend/package-lock.json`

- [x] **Step 1: Install exact frontend dependencies**

Run: `cd frontend && npm ci`

Expected: installation succeeds from the branch lock file.

- [x] **Step 2: Run the backend baseline**

Run: `python -m pytest -q`

Expected: the branch's backend suite passes before integration.

- [x] **Step 3: Run the frontend baseline**

Run: `cd frontend && npm run lint && npm test && npm run build && npm run test:e2e`

Expected: lint, unit tests, production build, and browser tests pass before integration.

### Task 2: Merge the current main branch

**Files:**

- Resolve: `app/routers/imports.py`
- Resolve: `app/services/video_note_markdown.py`
- Resolve: `frontend/components/video-notes/VideoNoteWorkspace.ai.test.tsx`
- Resolve: `frontend/components/video-notes/VideoNoteWorkspace.tsx`
- Resolve: `frontend/components/video-notes/useVideoNoteAiEditing.test.tsx`
- Resolve: `tests/frontend_structure/test_video_note_component_boundaries.py`

- [x] **Step 1: Merge without rewriting branch history**

Run: `git merge main`

Expected: Git reports the six predicted content conflicts and auto-merges non-overlapping files.

- [x] **Step 2: Resolve backend import and Markdown conflicts**

Preserve the feature branch's completed multi-part/video-note workflows and the main branch's later import-task orchestration, Markdown identity reconciliation, and security corrections. Remove every conflict marker and keep public schemas/API responses backward compatible.

- [x] **Step 3: Resolve frontend workspace and test conflicts**

Preserve the feature branch's AI overwrite/source UI, stable block reconciliation, selection behavior, and performance work while retaining main's newer multi-part import integration, auth/layout guards, and test isolation. Keep the component-boundary test aligned with the resulting module split.

- [x] **Step 4: Confirm the merge is structurally complete**

Run: `git diff --check && git diff --name-only --diff-filter=U`

Expected: no whitespace errors, conflict markers, or unmerged paths.

### Task 3: Validate the combined branch

**Files:**

- Test: `tests/test_imports.py`
- Test: `tests/test_video_notes.py`
- Test: `tests/test_video_note_markdown.py`
- Test: `tests/test_dev_python_selection.py`
- Test: `tests/test_ci_workflow.py`
- Test: `frontend/components/video-notes/*.test.ts*`
- Test: `frontend/components/ImportModal.test.tsx`

- [x] **Step 1: Run focused backend integration tests**

Run: `python -m pytest tests/test_imports.py tests/test_video_notes.py tests/test_video_note_markdown.py tests/test_video_note_chapters.py tests/test_dev_python_selection.py tests/test_dev_script_boundaries.py tests/test_ci_workflow.py tests/test_dependency_security_policy.py -q`

Expected: all focused integration and policy tests pass.

- [x] **Step 2: Run the full backend suite**

Run: `python -m pytest -q`

Expected: all backend tests pass.

- [x] **Step 3: Run the complete frontend verification**

Run: `cd frontend && npm ci && npm audit --omit=dev --audit-level=high && npm run lint && npm test && npm run build && npm run test:e2e`

Expected: production audit reports zero vulnerabilities and all frontend checks pass.

- [x] **Step 4: Review the combined diff**

Run: `git diff --check && git status --short && git log --oneline --decorate -5`

Expected: the merge is committed, the worktree is clean, and review finds no unresolved Critical or Important issue.

### Task 4: Merge to main and clean up

**Files:**

- Integrate: `agent/video-note-ui-polish`

- [x] **Step 1: Merge the verified branch into main**

Run from the main worktree: `git merge --no-ff agent/video-note-ui-polish`

Expected: merge succeeds without new conflicts because the feature branch already contains the current main.

- [x] **Step 2: Re-run focused policy and frontend verification on main**

Run: `python -m pytest tests/test_ci_workflow.py tests/test_dependency_security_policy.py -q`

Run: `cd frontend && npm audit --omit=dev --audit-level=high && npm run lint && npm test && npm run build && npm run test:e2e`

Expected: all commands pass on the merged main branch.

- [x] **Step 3: Remove the clean, merged worktree and local feature branch**

Run from the main worktree: `git worktree remove .worktrees/video-note-ui-polish && git worktree prune && git branch -d agent/video-note-ui-polish`

Expected: only the main worktree remains and `git status --short` is empty.
