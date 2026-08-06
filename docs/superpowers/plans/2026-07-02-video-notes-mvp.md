# Video Notes MVP Implementation Plan

**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement private video-centered learning notes with a scoped backend API, Markdown export, a workspace-level note drawer, lightweight block editing, auto-save, source/chat entry points, and AI suggestion plumbing.

**Architecture:** Video notes are a focused domain with separate ORM, schema, router, runtime, presenter, Markdown, and AI helper modules. The frontend owns video-note state at the workspace layer and keeps `ChatPanel`, `SourcesPanel`, and source-list components as callback-only entry points. The MVP uses explicit JSON blocks so the editor can later migrate to a richer engine without changing persistence.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite JSON columns, Pydantic, Next.js 16, React 19, TypeScript, Vitest, Pytest.

---

## File Map

- Create `app/models_notes.py` for `VideoNote`.
- Modify `app/models.py` to re-export `VideoNote`.
- Modify `app/routers/__init__.py` and `app/main.py` to register `video_notes`.
- Create `app/schemas/video_notes.py` for note blocks, list/detail, save, AI, and export DTOs.
- Create `app/services/video_note_presenters.py` for scoped video lookup, note list presentation, and template seeding.
- Create `app/services/video_note_markdown.py` for block-to-Markdown and safe filename rendering.
- Create `app/services/video_note_ai.py` for deterministic fallback AI edit/summary operation shaping and injected model hook points.
- Create `app/services/video_note_route_runtime.py` for route orchestration.
- Create `app/routers/video_notes.py` as a thin route wrapper.
- Add backend behavior tests in `tests/test_video_notes.py`.
- Add backend boundary tests in `tests/service_boundaries/test_video_note_boundaries.py`.
- Add frontend API types/client in `frontend/lib/api/videoNoteTypes.ts` and `frontend/lib/api/videoNotes.ts`; update `frontend/lib/api.ts`.
- Create `frontend/components/video-notes/*` focused components and hooks.
- Modify `frontend/app/useWorkspaceState.ts`, `frontend/app/page.tsx`, `frontend/app/WorkspaceSidebar.tsx`, `frontend/app/WorkspaceCornerTools.tsx`, `frontend/components/SourcesPanel.tsx`, `frontend/components/sources/SourcesFolderList.tsx`, and `frontend/components/chat/MessageSources.tsx` only for state wiring and callbacks.
- Add styles in `frontend/app/styles/video-notes.css`; import from `frontend/app/globals.css`.
- Add frontend tests in `frontend/components/video-notes/*.test.tsx`, `frontend/components/SourcesPanel.test.tsx`, `frontend/components/ChatPanel.test.tsx` only as needed for callback wiring.
- Add frontend structure tests in `tests/frontend_structure/test_video_note_component_boundaries.py`.

## Task 1: Backend Model And Boundary Guards

**Files:**

- Create: `app/models_notes.py`
- Modify: `app/models.py`
- Test: `tests/test_model_module_exports.py`
- Test: `tests/service_boundaries/test_model_boundaries.py`
- Test: `tests/service_boundaries/test_video_note_boundaries.py`

- [x] **Step 1: Write failing model export and boundary tests**

Add tests proving `VideoNote` exists in `models_notes.py`, shares `Base.metadata`, and is only re-exported from `app.models`.

- [x] **Step 2: Run RED tests**

Run:

```powershell
python -m pytest tests\test_model_module_exports.py tests\service_boundaries\test_model_boundaries.py tests\service_boundaries\test_video_note_boundaries.py -q
```

Expected: fail because `app.models_notes` and `VideoNote` do not exist.

- [x] **Step 3: Implement `VideoNote` model and re-export**

Create `VideoNote` with the fields and unique constraint from the spec.

- [x] **Step 4: Run GREEN tests**

Run the same pytest command and expect all selected tests to pass.

## Task 2: Backend Schemas, Markdown, Presenters, Runtime, And Router

**Files:**

- Create: `app/schemas/video_notes.py`
- Create: `app/services/video_note_markdown.py`
- Create: `app/services/video_note_presenters.py`
- Create: `app/services/video_note_ai.py`
- Create: `app/services/video_note_route_runtime.py`
- Create: `app/routers/video_notes.py`
- Modify: `app/routers/__init__.py`
- Modify: `app/main.py`
- Test: `tests/test_video_notes.py`
- Test: `tests/service_boundaries/test_video_note_boundaries.py`

- [x] **Step 1: Write failing API tests**

Cover login requirement, user isolation, knowledge-base ownership, standard and blank note creation, save, list filters, optional body search, Markdown export, and AI endpoints returning operations without mutating notes.

- [x] **Step 2: Run RED API tests**

Run:

```powershell
python -m pytest tests\test_video_notes.py tests\service_boundaries\test_video_note_boundaries.py -q
```

Expected: fail because `/video-notes` routes are not registered.

- [x] **Step 3: Implement schemas and route runtime**

Use route runtime functions for list/read/create/update/export/AI. Keep route functions thin.

- [x] **Step 4: Implement scoped video lookup and templates**

Use `FavoriteVideo`, `FavoriteFolder`, `VideoCache`, and title helpers to seed standard note blocks and list state.

- [x] **Step 5: Implement Markdown export**

Serialize frontmatter, block types, timestamp links, and safe filenames from the saved note and scoped video metadata.

- [x] **Step 6: Implement AI operation plumbing**

Return structured summary/edit/tag operations. Do not persist note changes inside AI endpoints.

- [x] **Step 7: Run GREEN backend tests**

Run:

```powershell
python -m pytest tests\test_video_notes.py tests\service_boundaries\test_video_note_boundaries.py tests\test_database_migration.py tests\test_model_module_exports.py -q
```

Expected: pass.

## Task 3: Frontend API Client And Pure Editor Helpers

**Files:**

- Create: `frontend/lib/api/videoNoteTypes.ts`
- Create: `frontend/lib/api/videoNotes.ts`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/video-notes/videoNoteBlocks.ts`
- Create: `frontend/components/video-notes/useVideoNoteAutosave.ts`
- Create: `frontend/components/video-notes/useVideoNoteAiEditing.ts`
- Test: `frontend/lib/api/__tests__/videoNotes.test.ts`
- Test: `frontend/components/video-notes/videoNoteBlocks.test.ts`
- Test: `frontend/components/video-notes/useVideoNoteAutosave.test.tsx`
- Test: `frontend/components/video-notes/useVideoNoteAiEditing.test.tsx`

- [x] **Step 1: Write failing frontend tests**

Cover API path/method/query shapes, block operations, debounced save status, and AI undo snapshots.

- [x] **Step 2: Run RED frontend tests**

Run:

```powershell
npm --prefix frontend test -- videoNotes.test.ts videoNoteBlocks.test.ts useVideoNoteAutosave.test.tsx useVideoNoteAiEditing.test.tsx
```

Expected: fail because modules do not exist.

- [x] **Step 3: Implement API types and client**

Mirror backend schema names and export through `frontend/lib/api.ts`.

- [x] **Step 4: Implement block helper functions**

Support add, update, remove, move up, move down, convert, and markdown-ish text extraction for search display.

- [x] **Step 5: Implement autosave and AI editing hooks**

Use debounced saves, stable callbacks, and a visible AI undo stack.

- [x] **Step 6: Run GREEN frontend helper tests**

Run the same npm test command and expect all selected tests to pass.

## Task 4: Frontend Video Note Workspace

**Files:**

- Create: `frontend/components/video-notes/VideoNoteWorkspace.tsx`
- Create: `frontend/components/video-notes/VideoNoteDrawer.tsx`
- Create: `frontend/components/video-notes/VideoNoteHeader.tsx`
- Create: `frontend/components/video-notes/VideoNoteListPanel.tsx`
- Create: `frontend/components/video-notes/VideoNoteTemplatePicker.tsx`
- Create: `frontend/components/video-notes/VideoNoteBlockEditor.tsx`
- Create: `frontend/components/video-notes/VideoNoteBlock.tsx`
- Create: `frontend/components/video-notes/VideoNoteBlockToolbar.tsx`
- Create: `frontend/components/video-notes/VideoNoteToolRail.tsx`
- Create: `frontend/components/video-notes/VideoNoteAiPanel.tsx`
- Create: `frontend/components/video-notes/VideoNoteExportPanel.tsx`
- Create: `frontend/app/styles/video-notes.css`
- Modify: `frontend/app/globals.css`
- Test: `frontend/components/video-notes/VideoNoteWorkspace.test.tsx`
- Test: `frontend/components/video-notes/VideoNoteBlockEditor.test.tsx`

- [x] **Step 1: Write failing component tests**

Cover list loading, template creation, block editing, add/delete/up/down, save status, export copy/download controls, drawer/fullscreen toggle, and AI undo UI.

- [x] **Step 2: Run RED component tests**

Run:

```powershell
npm --prefix frontend test -- VideoNoteWorkspace.test.tsx VideoNoteBlockEditor.test.tsx
```

Expected: fail because components do not exist.

- [x] **Step 3: Implement focused components**

Keep large JSX split across the listed components. Avoid nested card layouts and keep mobile full-screen behavior explicit.

- [x] **Step 4: Add video note styles**

Keep styles in `video-notes.css`; do not add feature styles to large global sections.

- [x] **Step 5: Run GREEN component tests**

Run the same npm test command and expect pass.

## Task 5: Workspace And Entry Point Wiring

**Files:**

- Modify: `frontend/app/useWorkspaceState.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/WorkspaceSidebar.tsx`
- Modify: `frontend/app/WorkspaceCornerTools.tsx`
- Modify: `frontend/components/NotesSidebarPanel.tsx`
- Modify: `frontend/components/SourcesPanel.tsx`
- Modify: `frontend/components/sources/SourcesFolderList.tsx`
- Modify: `frontend/components/chat/MessageSources.tsx`
- Test: `frontend/app/page.test.tsx`
- Test: `frontend/components/NotesSidebarPanel.test.tsx`
- Test: `frontend/components/SourcesPanel.test.tsx`
- Test: `frontend/components/ChatPanel.test.tsx`
- Test: `tests/frontend_structure/test_video_note_component_boundaries.py`

- [x] **Step 1: Write failing wiring and structure tests**

Cover notes sidebar opening the note list, source video note callbacks, chat source note callbacks, and absence of video note API imports in `ChatPanel` and `SourcesPanel`.

- [x] **Step 2: Run RED wiring tests**

Run:

```powershell
python -m pytest tests\frontend_structure\test_video_note_component_boundaries.py -q
npm --prefix frontend test -- page.test.tsx NotesSidebarPanel.test.tsx SourcesPanel.test.tsx ChatPanel.test.tsx
```

Expected: fail because callbacks and workspace state do not exist.

- [x] **Step 3: Wire workspace state and callbacks**

Add `activeVideoNote`, `videoNoteMode`, open/close/fullscreen handlers, and pass callback-only props into source/chat/list components.

- [x] **Step 4: Run GREEN wiring tests**

Run the same commands and expect pass.

## Task 6: Targeted Regressions And Full Verification

**Files:**

- All changed files.

- [x] **Step 1: Run backend targeted tests**

```powershell
python -m pytest tests\test_video_notes.py tests\service_boundaries\test_video_note_boundaries.py tests\service_boundaries tests\test_model_module_exports.py tests\test_database_migration.py -q
```

- [x] **Step 2: Run frontend targeted tests**

```powershell
npm --prefix frontend test -- videoNotes.test.ts videoNoteBlocks.test.ts useVideoNoteAutosave.test.tsx useVideoNoteAiEditing.test.tsx VideoNoteWorkspace.test.tsx VideoNoteBlockEditor.test.tsx page.test.tsx NotesSidebarPanel.test.tsx SourcesPanel.test.tsx ChatPanel.test.tsx
```

- [x] **Step 3: Run lint and build**

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

- [x] **Step 4: Run full repository verification**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
```

- [x] **Step 5: Commit implementation**

Commit after all checks pass, then merge back to `main` with `git merge --ff-only` and rerun targeted regressions on `main`.
