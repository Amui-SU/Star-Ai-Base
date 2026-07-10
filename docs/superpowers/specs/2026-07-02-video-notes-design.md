# Video Notes Design

## Goal

Build the first vertical slice of video-centered learning notes for Zhiku Cloud.
Each note is a private, editable, Markdown-exportable study document bound to one
video in one knowledge base.

The MVP should let a user open a video note from the source list, the notes
entry, or a chat source; create a standard or blank note; edit Markdown-native
blocks; auto-save; use AI to generate and edit learning content with visible
undo; and export one note as Markdown.

## Non-Goals For The MVP

- Shared notes, workspace collaboration, comments, permissions, or conflict
  resolution.
- Putting note contents into Chroma or normal RAG answers.
- Batch export, Obsidian vault writes, Notion sync, or Feishu sync.
- Rich Notion-style blocks such as tables, columns, images, databases, embeds,
  or canvas layouts.
- Full editor replacement with Tiptap, Lexical, or ProseMirror.
- Broad learning-review features beyond one-video notes.

## Product Scope

The note's ownership boundary is:

```text
user_id + workspace_id + knowledge_base_id + bvid
```

The same video can have different notes in different knowledge bases. Different
users never share the same note in this MVP.

The user can open a video note from three places:

- A "笔记" action on each video item in the source/favorites video list.
- The workspace notes entry, which shows a current-knowledge-base note list and
  supports knowledge base switching.
- A "记笔记" action on chat source links when the source contains a BVID.

On desktop, a video note opens as a right-side half-screen workspace, with a
manual full-screen option and an adjustable width if the current workspace shell
can support it cleanly. On mobile, it opens full-screen by default.

The video note list is scoped to the selected knowledge base. It shows the video
title, source folder, note existence, last edit time, and learning-summary status.
It supports search by title, BVID, and tags. If the user enables note-body search,
the search also scans the user's own note text in the current knowledge base.
Note-body search remains plain database text search for the MVP and does not
affect RAG.

## Initial Note Templates

When a note does not exist, the user chooses one of two templates:

- Standard video learning template.
- Blank note.

The standard template contains:

- Source information.
- AI summary.
- Key points.
- Timestamp outline.
- My notes.
- Questions and todos.

Existing `VideoCache.content` and `VideoCache.outline_json` seed the initial AI
summary and timestamp outline when available. The user can regenerate a more
study-oriented summary later.

Future versions may add user-defined templates and official template updates.
The MVP should not build template management UI.

## Backend Architecture

Video notes are an independent domain. Do not add learning-note orchestration to
`chat`, `knowledge_bases`, or legacy source routes.

Add focused modules:

- `app/models_notes.py`: SQLAlchemy ORM models for video notes.
- `app/schemas/video_notes.py`: Pydantic request and response schemas.
- `app/routers/video_notes.py`: thin FastAPI router with parameters,
  dependencies, response models, and service delegation.
- `app/services/video_note_route_runtime.py`: route orchestration for listing,
  creation, saving, AI operations, and export.
- `app/services/video_note_presenters.py`: response shaping, source folder
  labels, display titles, and list-state mapping.
- `app/services/video_note_markdown.py`: Markdown and filename rendering.
- `app/services/video_note_ai.py`: AI summary, edit, and tag suggestion behavior.

`app/models.py` may re-export `VideoNote` for compatibility, but the ORM class
must live in `app/models_notes.py`. Add structure tests so the model and route
logic do not drift back into broad modules.

## Data Model

Create `video_notes`:

```text
id
user_id
workspace_id
knowledge_base_id
bvid
source_binding_id nullable
title
template_id
blocks_json
tags_json
summary_status
summary_generated_at nullable
export_filename_template nullable
created_at
updated_at
```

Add a unique constraint on:

```text
user_id + workspace_id + knowledge_base_id + bvid
```

`blocks_json` stores editor-independent blocks. The MVP block set is:

- `heading`
- `paragraph`
- `bulleted_list`
- `todo`
- `quote`
- `ai_summary`
- `key_points`
- `timestamp_outline`
- `questions`
- `divider`

The block schema should remain explicit and versionable so a later Tiptap,
Lexical, or ProseMirror editor can map to and from the same saved note model.

## API Shape

Expose:

- `GET /video-notes?knowledge_base_id=&q=&tag=&include_body_search=`
  Lists video notes and note-ready videos for the current knowledge base.
- `GET /video-notes/{knowledge_base_id}/{bvid}`
  Returns an existing note or video metadata plus creation options.
- `POST /video-notes`
  Creates a note from the standard or blank template.
- `PUT /video-notes/{note_id}`
  Saves title, blocks, tags, and export filename template.
- `POST /video-notes/{note_id}/generate-summary`
  Returns study-oriented summary content and tag suggestions.
- `POST /video-notes/{note_id}/ai-edit`
  Returns proposed edit operations for selected blocks or the whole note
  context.
- `POST /video-notes/{note_id}/export/markdown`
  Returns Markdown content and a suggested safe filename.

Every endpoint must authenticate the system user and validate that the knowledge
base belongs to the current workspace. Video access must be scoped to the current
knowledge base by reusing existing `VideoCache`, `FavoriteVideo`,
source-binding, and display-title helpers rather than duplicating video
presentation rules.

## Frontend Architecture

Video notes should be managed at the workspace level, not inside `ChatPanel`,
`SourcesPanel`, or `ChatHistorySidebarPanel`.

Add API modules:

- `frontend/lib/api/videoNotes.ts`
- `frontend/lib/api/videoNoteTypes.ts`

Re-export them from `frontend/lib/api.ts`.

Add focused UI modules under:

```text
frontend/components/video-notes/
```

Recommended files:

- `VideoNoteWorkspace.tsx`
- `VideoNoteDrawer.tsx`
- `VideoNoteHeader.tsx`
- `VideoNoteListPanel.tsx`
- `VideoNoteTemplatePicker.tsx`
- `VideoNoteBlockEditor.tsx`
- `VideoNoteBlock.tsx`
- `VideoNoteBlockToolbar.tsx`
- `VideoNoteToolRail.tsx`
- `VideoNoteAiPanel.tsx`
- `VideoNoteExportPanel.tsx`
- `useVideoNoteState.ts`
- `useVideoNoteAutosave.ts`
- `useVideoNoteAiEditing.ts`
- `videoNoteMarkdown.ts` if a frontend preview helper is needed

Workspace state should hold the active video note:

```ts
type ActiveVideoNote = null | {
  knowledgeBaseId: number;
  bvid: string;
  source: "sources" | "notes" | "chat";
};
```

The UI mode is:

```ts
type VideoNoteMode = "drawer" | "fullscreen";
```

`SourcesFolderList` and `MessageSources` should only emit open-note callbacks.
They should not fetch or save video notes directly.

## Block Editor Behavior

The MVP uses a lightweight self-owned block editor over the explicit
`blocks_json` model. It supports:

- Editing text or list items in supported block types.
- Adding blocks through a simple add-block menu.
- Moving blocks up and down.
- Deleting blocks.
- Converting between compatible block types where safe.

No drag-and-drop is required in the MVP. Desktop drag-and-drop can be added later
without changing the saved block model.

Manual text editing uses normal browser/editor undo and redo shortcuts. AI
changes use separate visible undo actions.

## Focused Workspace Editor Interactions

The focused video-note workspace uses the Markdown editor as the primary writing
surface. The left tool rail should expose commands that have immediate note-level
value:

- `笔记名称` opens a small dialog for editing the note title. Empty titles are not
  saved.
- `添加待办` inserts a todo block.
- Export actions reuse the backend Markdown export response for copy and
  download feedback.

Editor toolbar tooltips remain available on hover-capable devices, including
narrow desktop windows. Tooltip hiding should be based on coarse touch input,
not only viewport width.

Clickable note content is constrained to the visible clickable text:

- Markdown links open only when the anchor text itself is clicked.
- Plain `http://` and `https://` URLs open only when the click lands on the URL
  text, not the rest of the containing line.
- Timestamp links open only from the rendered timestamp span.

## Auto-Save

`useVideoNoteAutosave` saves edited note state with debounce. It shows:

- Saving.
- Saved.
- Save failed.
- Connection unavailable or offline.

Failed saves must not clear local note state. The user can retry or continue
editing until the next successful save.

Each video has only one current note version in the MVP. Full version history and
per-block history are future features.

## AI Summary And Editing

AI behavior uses the current user's AI credentials, following the existing
user-owned API key policy.

Summary generation uses only:

- Current video summary, transcript, or outline.
- Current note blocks.

It should not retrieve unrelated videos or the whole knowledge base.

The summary response is structured:

- Summary.
- Key points.
- Questions.
- Tag suggestions.
- Optional timestamp outline revisions.

Tag suggestions are not added until the user confirms them.

AI editing supports fixed actions and free-form instructions:

- Summarize selected block.
- Polish.
- Expand.
- Compress.
- Convert to todos.
- Generate key points.
- Generate questions.
- Suggest tags.
- Free instruction.

AI edit modes:

- Suggest then confirm.
- Directly edit selected blocks.
- Insert new blocks.

AI endpoints return structured suggestions or edit operations. They do not
persist note changes directly. The frontend previews or applies the returned
operations, records an AI undo snapshot, and then persists the resulting note
through the normal save endpoint.

Before applying an AI change, the frontend stores a snapshot of affected note
state. The UI displays a visible operation record such as "AI 已润色 1 个段落块"
with an undo action. Consecutive AI undo is supported for recent AI operations.

If an AI request fails, no note state changes. If structured parsing fails, show
the raw text and allow inserting it as a paragraph.

## Markdown Export

The backend owns Markdown export through `video_note_markdown.py`; the frontend
uses the returned Markdown for copy and `.md` download.

The MVP exports one note at a time and does not zip multiple files.

Frontmatter example:

```md
---
source: bilibili
bvid: BV...
title: 视频标题
up: UP 主
knowledge_base: 当前知识库
tags: [AI, 课程]
url: https://www.bilibili.com/video/BV...
created: 2026-07-02
updated: 2026-07-02
---
```

Timestamp outline items export as visible time text plus a Bilibili timestamp
link:

```md
- [03:24](https://www.bilibili.com/video/BV...?t=204) 讲解核心概念
```

The default filename template is:

```text
{{title}} - {{bvid}}.md
```

Supported filename variables:

- `{{title}}`
- `{{bvid}}`
- `{{up}}`
- `{{knowledge_base}}`
- `{{date}}`

The renderer cleans unsafe filename characters and falls back to BVID when the
title is empty.

## External Integration Path

The MVP is Obsidian-friendly because it emits standard Markdown and frontmatter.
It does not write directly into a vault.

Future batch export should reuse the same Markdown renderer for many notes, then
apply the filename or path template and zip the results.

Future Notion sync can map note metadata to page or database properties and
convert Markdown or block JSON into Notion pages.

Future Feishu sync can first export Markdown and use Drive import tasks to create
cloud documents, storing the returned document token for later updates.

If sync metadata is needed later, add an independent table such as:

```text
video_note_sync_targets
note_id
provider
external_id
sync_status
last_synced_at
last_error
```

Do not build this table in the MVP unless a sync feature is actually
implemented.

## Implementation Slices

Implementation must follow small vertical slices:

1. Backend model, schemas, list/read/create/save, and Markdown export.
2. Frontend note list, drawer/fullscreen workspace, template creation,
   block editor, and auto-save.
3. Open-note entries from source videos, note list, and chat sources.
4. AI summary generation, AI editing, tag suggestions, and visible AI undo.
5. Hardening: structure tests, mobile layout, export filename edge cases, and
   focused regressions.

Each slice should use its own worktree, tests first for changed behavior or
boundaries, targeted regressions, and the repository verification workflow before
commit.

## Testing Strategy

Backend tests:

- User authentication and user isolation.
- Knowledge base ownership checks.
- Video visibility scoped to the selected knowledge base.
- Create standard and blank notes.
- Auto-save payload validation.
- List filters by query and tag.
- Optional body search only when enabled.
- Markdown export for frontmatter, tags, block types, filenames, and timestamp
  links.
- AI endpoints do not mutate notes on failure.

Frontend tests:

- Note list loads for the active knowledge base and can switch knowledge bases.
- Template picker creates standard and blank notes.
- Drawer/fullscreen behavior on desktop and mobile conditions.
- Block editing, add, delete, up/down movement, and save status.
- Copy/download Markdown uses backend export output.
- AI operation records can undo applied AI changes.
- Source list and chat source entries only call open-note callbacks.

Structure tests:

- `video_notes.py` router delegates orchestration to services.
- `VideoNote` ORM lives in `models_notes.py`, not `models.py`.
- Video note response shaping lives in presenter/service modules.
- `ChatPanel.tsx` does not import video note API or manage video note state.
- `SourcesPanel.tsx` does not fetch or save video notes.
- Video note component tests stay in focused files rather than broad sentinel
  files.

## Open Questions

No product-blocking questions remain for the MVP design. The main implementation
choice still to confirm during planning is the exact first slice boundary and
test order.
