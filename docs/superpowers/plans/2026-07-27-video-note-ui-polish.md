# Video Note UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the four remaining video-note UI polish items: structured AI result provenance, safe overwrite confirmation, consistent video timestamp formatting, and debounced race-safe note search.

**Architecture:** Keep AI provenance in the transient AI response instead of persisted note blocks. Put pure frontend decisions in focused helpers, leave request orchestration in `VideoNoteWorkspace`, and render the result card and confirmation dialog through focused video-note components. Separate the live search input from the effective query and guard list writes with a monotonically increasing request id.

**Tech Stack:** FastAPI, Pydantic, pytest, React 19, TypeScript, Vitest, Testing Library, Next.js 16, CSS, Playwright.

---

## Existing worktree safety

The checkout already contains uncommitted work in several files this plan must touch. Preserve it.

- Before editing a file, inspect `git diff -- <path>`.
- Never use `git add -A` or stage an entire overlapping file without reviewing its complete diff.
- Use `git add -p -- <paths>` to stage only this plan's hunks. If a new hunk cannot be separated from pre-existing work, leave the task uncommitted and record the overlap instead of capturing unrelated changes.
- Do not restore, reset, or rewrite pre-existing changes.

## File map

- `app/schemas/video_notes.py`: public AI response source type and field.
- `app/services/video_note_ai_suggestions.py`: internal AI status to public source mapping.
- `tests/test_video_note_ai_suggestions.py`: pure backend provenance mapping tests.
- `tests/test_video_notes.py`: endpoint contract assertions.
- `frontend/lib/api/videoNoteTypes.ts`: frontend response source union.
- `frontend/lib/api.ts`: export the new response source union from the API barrel.
- `frontend/components/video-notes/videoNoteAiUi.ts`: pure action targets, non-empty-block detection, and result-card presentation.
- `frontend/components/video-notes/videoNoteAiUi.test.ts`: pure helper tests.
- `frontend/components/video-notes/VideoNoteAiOverwriteDialog.tsx`: accessible application confirmation dialog.
- `frontend/components/video-notes/VideoNoteAiPanel.tsx`: AI buttons and provenance status card.
- `frontend/components/video-notes/VideoNoteWorkspace.tsx`: confirmation gate, AI request state, debounce, and request race protection.
- `frontend/components/video-notes/VideoNoteWorkspaceView.tsx`: typed data flow into the AI panel.
- `frontend/components/video-notes/VideoNoteWorkspace.ai.test.tsx`: status card, confirmation, cancellation, application, and video-switch coverage.
- `frontend/components/video-notes/VideoNoteWorkspace.selection.test.tsx`: debounce and stale-response coverage.
- `frontend/components/video-notes/videoNoteTime.ts`: frontend timestamp formatter.
- `frontend/components/video-notes/videoNoteTime.test.ts`: formatter contract.
- `frontend/components/video-notes/videoNoteMarkdownAdapter.ts`: use the shared formatter.
- `frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts`: Markdown serialization coverage.
- `app/services/video_note_markdown.py`: safe backend timestamp coercion while preserving the existing format.
- `tests/test_video_note_markdown.py`: backend formatter contract.
- `frontend/app/styles/video-notes/side-panels.css`: result-card and confirmation-dialog desktop styles.
- `frontend/app/styles/video-notes/responsive.css`: mobile dialog/card adjustments.
- `frontend/components/video-notes/VideoNoteStyles.test.ts`: CSS boundary assertions.

### Task 1: Add structured AI result provenance

**Files:**

- Modify: `app/schemas/video_notes.py`
- Modify: `app/services/video_note_ai_suggestions.py`
- Modify: `tests/test_video_note_ai_suggestions.py`
- Modify: `tests/test_video_notes.py`
- Modify: `frontend/lib/api/videoNoteTypes.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Write failing backend mapping tests**

Add assertions to the existing suggestion tests so all four internal states prove their public source value:

```python
def test_summary_suggestions_expose_ai_result_source():
    response = build_summary_suggestions(
        VideoNote(blocks_json=[]),
        _source(),
        ai_payload={"summary": "模型摘要"},
        ai_status="generated",
    )
    assert response.result_source == "ai"


def test_ai_result_sources_map_official_and_fallback_states():
    note = VideoNote(blocks_json=[])
    request = VideoNoteAiEditRequest(
        action="generate_timestamps",
        instruction=None,
        selected_block_ids=[],
    )
    assert build_ai_edit_suggestions(
        note,
        request,
        _source(),
        ai_status="official",
        bilibili_timestamps=[{"time": 12, "text": "章节"}],
    ).result_source == "official"
    assert build_ai_edit_suggestions(
        note, request, _source(), ai_status="unavailable"
    ).result_source == "fallback"
    assert build_ai_edit_suggestions(
        note, request, _source(), ai_status="failed"
    ).result_source == "fallback"
```

In `tests/test_video_notes.py`, extend one summary response and one official timestamp response assertion:

```python
assert summary.json()["result_source"] == "ai"
assert timestamps.json()["result_source"] == "official"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_video_note_ai_suggestions.py tests/test_video_notes.py -q
```

Expected: FAIL because `VideoNoteAiResponse` has no `result_source` attribute or serialized field.

- [ ] **Step 3: Add the response type and mapping helper**

In `app/schemas/video_notes.py`:

```python
from typing import Literal

VideoNoteAiResultSource = Literal["ai", "official", "fallback"]


class VideoNoteAiResponse(BaseModel):
    operations: list[VideoNoteAiOperation]
    tag_suggestions: list[str] = Field(default_factory=list)
    message: str
    result_source: VideoNoteAiResultSource
```

In `app/services/video_note_ai_suggestions.py`:

```python
from app.schemas.video_notes import VideoNoteAiResultSource


def _result_source_for(status: AiStatus) -> VideoNoteAiResultSource:
    if status == "generated":
        return "ai"
    if status == "official":
        return "official"
    return "fallback"
```

Pass `result_source=_result_source_for(ai_status)` to every `VideoNoteAiResponse(...)` construction in `build_summary_suggestions` and `build_ai_edit_suggestions`, including the generic edit branch and the empty-timestamp branch.

In `frontend/lib/api/videoNoteTypes.ts`:

```typescript
export type VideoNoteAiResultSource = "ai" | "official" | "fallback";

export interface VideoNoteAiResponse {
  operations: VideoNoteAiOperation[];
  tag_suggestions: string[];
  message: string;
  result_source: VideoNoteAiResultSource;
}
```

Add `VideoNoteAiResultSource` to the existing named type exports from
`./api/videoNoteTypes` in `frontend/lib/api.ts`.

- [ ] **Step 4: Run the backend tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_video_note_ai_suggestions.py tests/test_video_notes.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Review and commit only Task 1 hunks**

```powershell
git diff -- app/schemas/video_notes.py app/services/video_note_ai_suggestions.py tests/test_video_note_ai_suggestions.py tests/test_video_notes.py frontend/lib/api/videoNoteTypes.ts frontend/lib/api.ts
git add -p -- app/schemas/video_notes.py app/services/video_note_ai_suggestions.py tests/test_video_note_ai_suggestions.py tests/test_video_notes.py frontend/lib/api/videoNoteTypes.ts frontend/lib/api.ts
git diff --cached --check
git commit -m "feat: expose video note AI result source"
```

If pre-existing hunks cannot be separated, skip the commit and record the affected paths.

### Task 2: Add result cards and safe overwrite confirmation

**Files:**

- Create: `frontend/components/video-notes/videoNoteAiUi.ts`
- Create: `frontend/components/video-notes/videoNoteAiUi.test.ts`
- Create: `frontend/components/video-notes/VideoNoteAiOverwriteDialog.tsx`
- Modify: `frontend/components/video-notes/VideoNoteAiPanel.tsx`
- Modify: `frontend/components/video-notes/VideoNoteWorkspace.tsx`
- Modify: `frontend/components/video-notes/VideoNoteWorkspaceView.tsx`
- Modify: `frontend/components/video-notes/VideoNoteWorkspace.ai.test.tsx`
- Modify: `frontend/app/styles/video-notes/side-panels.css`
- Modify: `frontend/app/styles/video-notes/responsive.css`
- Modify: `frontend/components/video-notes/VideoNoteStyles.test.ts`

- [ ] **Step 1: Write failing pure helper tests**

Create `videoNoteAiUi.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  getAiOverwriteTargets,
  getAiResultPresentation,
} from "./videoNoteAiUi";

describe("video note AI UI rules", () => {
  it("only reports non-empty target blocks for overwrite confirmation", () => {
    expect(
      getAiOverwriteTargets(
        [
          { id: "ai-summary", type: "ai_summary", text: "已有摘要" },
          { id: "key-points", type: "key_points", items: [] },
        ],
        "summary",
      ),
    ).toEqual(["摘要"]);
    expect(getAiOverwriteTargets([], "timestamps")).toEqual([]);
  });

  it("maps structured sources to visible card content", () => {
    expect(getAiResultPresentation("ai").badge).toBe("AI 生成");
    expect(getAiResultPresentation("official").badge).toBe("官方章节");
    expect(getAiResultPresentation("fallback")).toMatchObject({
      badge: "智能兜底",
      className: "fallback",
    });
  });
});
```

- [ ] **Step 2: Run helper tests and verify RED**

Run:

```powershell
Push-Location frontend
npm test -- videoNoteAiUi.test.ts
Pop-Location
```

Expected: FAIL because `videoNoteAiUi.ts` does not exist.

- [ ] **Step 3: Implement the pure AI UI rules**

Create `videoNoteAiUi.ts`:

```typescript
import type { VideoNoteAiResultSource, VideoNoteBlock } from "@/lib/api";

export type VideoNoteAiAction = "summary" | "questions" | "timestamps";

const ACTION_TARGETS: Record<
  VideoNoteAiAction,
  Array<{ id: string; label: string }>
> = {
  summary: [
    { id: "ai-summary", label: "摘要" },
    { id: "key-points", label: "关键观点" },
  ],
  questions: [{ id: "questions", label: "复盘问题" }],
  timestamps: [{ id: "timestamp-outline", label: "时间戳提纲" }],
};

function hasBlockContent(block: VideoNoteBlock): boolean {
  if (String(block.text ?? "").trim()) return true;
  return (block.items ?? []).some((item) =>
    String(item.text ?? item.content ?? "").trim(),
  );
}

export function getAiOverwriteTargets(
  blocks: VideoNoteBlock[],
  action: VideoNoteAiAction,
): string[] {
  return ACTION_TARGETS[action]
    .filter((target) =>
      blocks.some((block) => block.id === target.id && hasBlockContent(block)),
    )
    .map((target) => target.label);
}

export function getAiResultPresentation(source: VideoNoteAiResultSource) {
  return {
    ai: { badge: "AI 生成", className: "ai", detail: "由 AI 模型生成" },
    official: {
      badge: "官方章节",
      className: "official",
      detail: "根据 B 站官方章节整理",
    },
    fallback: {
      badge: "智能兜底",
      className: "fallback",
      detail: "未使用 AI 模型，结果来自已有资料或规则整理，请核对",
    },
  }[source];
}
```

- [ ] **Step 4: Run helper tests and verify GREEN**

Run `npm test -- videoNoteAiUi.test.ts` from `frontend`.

Expected: the helper test file PASS.

- [ ] **Step 5: Write failing workspace interaction tests**

Extend `VideoNoteWorkspace.ai.test.tsx` with three focused tests:

```typescript
it("shows the structured AI result card after generation", async () => {
  const user = userEvent.setup();
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: baseNote.bvid,
        title: baseNote.title,
        has_note: true,
        note_id: baseNote.id,
        summary_status: "seeded",
        tags: [],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });
  vi.mocked(videoNoteApi.generateSummary).mockResolvedValue({
    result_source: "ai",
    message: "AI 摘要已生成",
    tag_suggestions: [],
    operations: [
      {
        kind: "replace_or_insert_block",
        target_block_id: "ai-summary",
        block: { id: "ai-summary", type: "ai_summary", text: "新摘要" },
      },
    ],
  });
  vi.mocked(videoNoteApi.aiEdit).mockImplementation(
    async (_noteId, payload) => ({
      result_source:
        payload.action === "generate_timestamps" ? "official" : "fallback",
      message:
        payload.action === "generate_timestamps"
          ? "官方章节已生成"
          : "已提供基础问题",
      tag_suggestions: [],
      operations: [],
    }),
  );
  renderWorkspace({ initialBvid: baseNote.bvid });
  await findMarkdownEditor();
  await user.click(screen.getByRole("button", { name: "生成摘要" }));
  expect(await screen.findByText("AI 生成")).toBeVisible();
  expect(screen.getByText("由 AI 模型生成")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "生成问题" }));
  expect(await screen.findByText("智能兜底")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "生成时间戳" }));
  expect(await screen.findByText("官方章节")).toBeVisible();
});

it("confirms or cancels before replacing a non-empty AI target block", async () => {
  const user = userEvent.setup();
  const noteWithSummary: typeof baseNote = {
    ...baseNote,
    blocks: [
      ...baseNote.blocks,
      { id: "ai-summary", type: "ai_summary", text: "已有摘要" },
    ],
  };
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: baseNote.bvid,
        title: baseNote.title,
        has_note: true,
        note_id: baseNote.id,
        summary_status: "seeded",
        tags: [],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: noteWithSummary,
    video,
    can_create: false,
  });
  vi.mocked(videoNoteApi.generateSummary).mockResolvedValue({
    result_source: "ai",
    message: "AI 摘要已生成",
    tag_suggestions: [],
    operations: [
      {
        kind: "replace_or_insert_block",
        target_block_id: "ai-summary",
        block: { id: "ai-summary", type: "ai_summary", text: "新摘要" },
      },
    ],
  });
  renderWorkspace({ initialBvid: baseNote.bvid });
  await findMarkdownEditor();

  await user.click(screen.getByRole("button", { name: "生成摘要" }));
  const firstDialog = screen.getByRole("dialog", { name: "覆盖现有内容？" });
  expect(within(firstDialog).getByText(/摘要/)).toBeVisible();
  expect(videoNoteApi.generateSummary).not.toHaveBeenCalled();
  await user.click(within(firstDialog).getByRole("button", { name: "取消" }));
  expect(videoNoteApi.generateSummary).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "撤销 AI 编辑" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "生成摘要" }));
  const secondDialog = screen.getByRole("dialog", { name: "覆盖现有内容？" });
  await user.click(
    within(secondDialog).getByRole("button", { name: "继续生成并覆盖" }),
  );
  expect(videoNoteApi.generateSummary).toHaveBeenCalledWith(baseNote.id);
});
```

Every mocked `VideoNoteAiResponse` in this file must include an explicit `result_source` value so TypeScript enforces the new contract.

- [ ] **Step 6: Run workspace tests and verify RED**

Run:

```powershell
Push-Location frontend
npm test -- VideoNoteWorkspace.ai.test.tsx
Pop-Location
```

Expected: FAIL because there is no structured status card or overwrite dialog.

- [ ] **Step 7: Implement dialog and workspace request gate**

Create `VideoNoteAiOverwriteDialog.tsx` using `ModalShell` and the existing
focus-trap hook:

```tsx
import { useRef } from "react";
import ModalShell from "@/components/ui/ModalShell";
import { useDialogFocusTrap } from "@/components/ui/useDialogFocusTrap";

interface Props {
  targets: string[];
  onCancel: () => void;
  onConfirm: () => void;
}

export default function VideoNoteAiOverwriteDialog({
  targets,
  onCancel,
  onConfirm,
}: Props) {
  const dialogRef = useRef<HTMLElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useDialogFocusTrap({
    containerRef: dialogRef,
    initialFocusRef: cancelRef,
    onEscape: onCancel,
  });
  return (
    <ModalShell cardClassName="video-note-ai-confirm" onClose={onCancel}>
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="覆盖现有内容？"
        tabIndex={-1}
      >
        <h3>覆盖现有内容？</h3>
        <p>将替换：{targets.join("、")}。生成后仍可撤销。</p>
        <div className="video-note-ai-confirm-actions">
          <button ref={cancelRef} type="button" onClick={onCancel}>
            取消
          </button>
          <button type="button" onClick={onConfirm}>
            继续生成并覆盖
          </button>
        </div>
      </section>
    </ModalShell>
  );
}
```

In `VideoNoteWorkspace.tsx`, add:

```typescript
const [aiResultSource, setAiResultSource] =
  useState<VideoNoteAiResultSource | null>(null);
const [pendingAiAction, setPendingAiAction] =
  useState<VideoNoteAiAction | null>(null);

const executeAiAction = async (action: VideoNoteAiAction) => {
  if (!note) return;
  const requestNoteId = note.id;
  const loadingMessage = {
    summary: "正在生成摘要...",
    questions: "正在生成复盘问题...",
    timestamps: "正在生成时间戳提纲...",
  }[action];
  setAiLoading(true);
  setAiResultSource(null);
  setAiMessage(loadingMessage);
  try {
    const response =
      action === "summary"
        ? await videoNoteApi.generateSummary(note.id)
        : await videoNoteApi.aiEdit(note.id, {
            action:
              action === "questions"
                ? "generate_questions"
                : "generate_timestamps",
            instruction: null,
            selected_block_ids: [],
          });
    if (noteIdRef.current !== requestNoteId) return;
    aiEditing.applyAiOperations(response.operations);
    if (action === "summary") {
      setTags((current) =>
        Array.from(new Set([...current, ...response.tag_suggestions])),
      );
    }
    setAiResultSource(response.result_source);
    setAiMessage(response.message);
    return response;
  } catch (error) {
    if (noteIdRef.current === requestNoteId) {
      setAiMessage(
        action === "summary"
          ? "生成摘要失败，请检查网络连接或稍后重试"
          : action === "questions"
            ? "生成问题失败，请检查网络连接或稍后重试"
            : "生成时间戳失败，请检查网络连接或稍后重试",
      );
    }
    console.error("视频笔记 AI 操作失败:", error);
  } finally {
    setAiLoading(false);
  }
};

const requestAiAction = (action: VideoNoteAiAction) => {
  const targets = getAiOverwriteTargets(blocks, action);
  if (targets.length > 0) {
    setPendingAiAction(action);
    return;
  }
  void executeAiAction(action);
};

const pendingOverwriteTargets = pendingAiAction
  ? getAiOverwriteTargets(blocks, pendingAiAction)
  : [];

const confirmAiOverwrite = () => {
  const action = pendingAiAction;
  setPendingAiAction(null);
  if (action) void executeAiAction(action);
};
```

Replace the three existing request bodies with this dispatcher and pass wrappers
`requestAiAction("summary")`, `requestAiAction("questions")`, and
`requestAiAction("timestamps")` to the view. On video switch, clear
`pendingAiAction` and `aiResultSource` in addition to the existing stale-response
and undo reset behavior.

Pass the source, pending target labels, confirm callback, and cancel callback through `VideoNoteWorkspaceView` into `VideoNoteAiPanel`. Render `VideoNoteAiOverwriteDialog` only while `pendingAiAction` is non-null.

- [ ] **Step 8: Render structured result cards and styles**

In `VideoNoteAiPanel.tsx`, replace the message-only paragraph with:

```tsx
const presentation = resultSource
  ? getAiResultPresentation(resultSource)
  : null;

{
  message && presentation ? (
    <div
      className={`video-note-ai-result ${presentation.className}`}
      role="status"
    >
      <span className="video-note-ai-result-badge">{presentation.badge}</span>
      <strong>{message}</strong>
      <small>{presentation.detail}</small>
    </div>
  ) : (
    <p className="video-note-ai-status" role="status">
      {message ?? "正在处理..."}
    </p>
  );
}
```

Add focused CSS classes in `side-panels.css` for neutral AI success, official-source, and warm-yellow fallback cards. Add a fixed-width confirmation card that collapses to `calc(100vw - 32px)` in `responsive.css`. Extend `VideoNoteStyles.test.ts` to assert the fallback class has a distinct background/border and the mobile confirmation card is viewport-safe.

- [ ] **Step 9: Run Task 2 tests and verify GREEN**

Run:

```powershell
Push-Location frontend
npm test -- videoNoteAiUi.test.ts VideoNoteWorkspace.ai.test.tsx VideoNoteStyles.test.ts
Pop-Location
```

Expected: all selected test files PASS.

- [ ] **Step 10: Review and commit only Task 2 hunks**

```powershell
git diff -- frontend/components/video-notes frontend/app/styles/video-notes/side-panels.css frontend/app/styles/video-notes/responsive.css
git add -p -- frontend/components/video-notes frontend/app/styles/video-notes/side-panels.css frontend/app/styles/video-notes/responsive.css
git diff --cached --check
git commit -m "feat: clarify video note AI results"
```

If overlapping existing hunks cannot be separated, defer the commit.

### Task 3: Unify video timestamp formatting

**Files:**

- Create: `frontend/components/video-notes/videoNoteTime.ts`
- Create: `frontend/components/video-notes/videoNoteTime.test.ts`
- Modify: `frontend/components/video-notes/videoNoteMarkdownAdapter.ts`
- Modify: `frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts`
- Modify: `app/services/video_note_markdown.py`
- Create: `tests/test_video_note_markdown.py`

- [ ] **Step 1: Write failing frontend and backend formatter tests**

Create `videoNoteTime.test.ts`:

```typescript
import { expect, it } from "vitest";
import { formatVideoTimestamp } from "./videoNoteTime";

it("formats video timestamps consistently", () => {
  expect(formatVideoTimestamp(204)).toBe("03:24");
  expect(formatVideoTimestamp(3723)).toBe("01:02:03");
  expect(formatVideoTimestamp(-1)).toBe("00:00");
  expect(formatVideoTimestamp(Number.NaN)).toBe("00:00");
});
```

Create `tests/test_video_note_markdown.py`:

```python
from app.services.video_note_markdown import _format_timestamp


def test_format_timestamp_uses_adaptive_padded_format():
    assert _format_timestamp(204) == "03:24"
    assert _format_timestamp(3723) == "01:02:03"
    assert _format_timestamp(-1) == "00:00"
    assert _format_timestamp("invalid") == "00:00"
```

Extend `videoNoteMarkdownAdapter.test.ts` so a timestamp-outline block serializes both values exactly:

```typescript
expect(
  blocksToMarkdown([
    {
      id: "timestamps",
      type: "timestamp_outline",
      items: [
        { time: 204, text: "核心概念" },
        { time: 3723, text: "总结" },
      ],
    },
  ]),
).toBe("- [03:24] 核心概念\n- [01:02:03] 总结");
```

- [ ] **Step 2: Run formatter tests and verify RED**

Run:

```powershell
python -m pytest tests/test_video_note_markdown.py -q
Push-Location frontend
npm test -- videoNoteTime.test.ts videoNoteMarkdownAdapter.test.ts
Pop-Location
```

Expected: backend fails on invalid string; frontend fails because the helper does not exist and existing formatting returns `3:24` / `62:03`.

- [ ] **Step 3: Implement shared frontend formatting and safe backend coercion**

Create `videoNoteTime.ts`:

```typescript
export function formatVideoTimestamp(value: unknown): string {
  const numeric = typeof value === "number" ? value : Number(value);
  const total = Number.isFinite(numeric) ? Math.max(0, Math.floor(numeric)) : 0;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = String(seconds).padStart(2, "0");
  return hours > 0
    ? `${String(hours).padStart(2, "0")}:${mm}:${ss}`
    : `${mm}:${ss}`;
}
```

Import it in `videoNoteMarkdownAdapter.ts` and remove the local `formatTimestamp` function.

In `app/services/video_note_markdown.py`:

```python
def _format_timestamp(seconds: Any) -> str:
    try:
        total_seconds = max(int(seconds or 0), 0)
    except (TypeError, ValueError):
        total_seconds = 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
```

- [ ] **Step 4: Run formatter tests and verify GREEN**

Run the commands from Step 2 again.

Expected: all selected tests PASS.

- [ ] **Step 5: Review and commit only Task 3 hunks**

```powershell
git diff -- app/services/video_note_markdown.py tests/test_video_note_markdown.py frontend/components/video-notes/videoNoteTime.ts frontend/components/video-notes/videoNoteTime.test.ts frontend/components/video-notes/videoNoteMarkdownAdapter.ts frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts
git add -p -- app/services/video_note_markdown.py frontend/components/video-notes/videoNoteMarkdownAdapter.ts frontend/components/video-notes/videoNoteMarkdownAdapter.test.ts
git add -- tests/test_video_note_markdown.py frontend/components/video-notes/videoNoteTime.ts frontend/components/video-notes/videoNoteTime.test.ts
git diff --cached --check
git commit -m "fix: unify video note timestamp formatting"
```

If the existing multipart URL hunks overlap, stage only formatter hunks or defer the commit.

### Task 4: Debounce note search and reject stale list responses

**Files:**

- Modify: `frontend/components/video-notes/VideoNoteWorkspace.tsx`
- Modify: `frontend/components/video-notes/VideoNoteWorkspace.selection.test.tsx`

- [ ] **Step 1: Write failing debounce test**

Add a test using fake timers and an empty first result:

```typescript
it("debounces note search for 300ms", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [],
  });
  renderWorkspace();
  await vi.runOnlyPendingTimersAsync();
  await user.click(screen.getByRole("button", { name: "选择笔记" }));
  const input = screen.getByRole("searchbox", { name: "搜索视频笔记" });
  await user.type(input, "学习");
  expect(videoNoteApi.list).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(299);
  expect(videoNoteApi.list).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(videoNoteApi.list).toHaveBeenLastCalledWith({
    knowledgeBaseId: 7,
    q: "学习",
    includeBodySearch: false,
  });
});
```

- [ ] **Step 2: Write failing stale-response and immediate-toggle tests**

Add this helper and controlled-response tests:

```typescript
import { act } from "@testing-library/react";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

it("ignores stale note-list responses", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  const oldRequest = deferred<Awaited<ReturnType<typeof videoNoteApi.list>>>();
  const newRequest = deferred<Awaited<ReturnType<typeof videoNoteApi.list>>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);
  renderWorkspace();
  await vi.advanceTimersByTimeAsync(0);
  await user.click(screen.getByRole("button", { name: "选择笔记" }));
  await user.type(
    screen.getByRole("searchbox", { name: "搜索视频笔记" }),
    "学习",
  );
  await vi.advanceTimersByTimeAsync(300);
  await act(async () => {
    newRequest.resolve({
      knowledge_base_id: 7,
      items: [
        {
          bvid: "BVNEW",
          title: "新搜索结果",
          has_note: false,
          summary_status: "not_created",
          tags: [],
        },
      ],
    });
  });
  expect(screen.getByText("新搜索结果")).toBeVisible();
  await act(async () => {
    oldRequest.resolve({
      knowledge_base_id: 7,
      items: [
        {
          bvid: "BVOLD",
          title: "过期结果",
          has_note: false,
          summary_status: "not_created",
          tags: [],
        },
      ],
    });
  });
  expect(screen.getByText("新搜索结果")).toBeVisible();
  expect(screen.queryByText("过期结果")).toBeNull();
});

it("applies body-search changes immediately", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [],
  });
  renderWorkspace();
  await vi.advanceTimersByTimeAsync(0);
  await user.click(screen.getByRole("button", { name: "选择笔记" }));
  await user.click(screen.getByRole("checkbox", { name: "搜索正文" }));
  await vi.advanceTimersByTimeAsync(0);
  expect(videoNoteApi.list).toHaveBeenLastCalledWith({
    knowledgeBaseId: 7,
    q: undefined,
    includeBodySearch: true,
  });
});
```

- [ ] **Step 3: Run selection tests and verify RED**

Run:

```powershell
Push-Location frontend
npm test -- VideoNoteWorkspace.selection.test.tsx
Pop-Location
```

Expected: debounce test observes per-keystroke calls or immediate call; stale response replaces the newer list.

- [ ] **Step 4: Implement effective query and request-id guard**

In `VideoNoteWorkspace.tsx`:

```typescript
const [query, setQuery] = useState("");
const [effectiveQuery, setEffectiveQuery] = useState("");
const listRequestIdRef = useRef(0);

useEffect(() => {
  listRequestIdRef.current += 1; // invalidate a request as soon as input changes
  const timer = window.setTimeout(() => setEffectiveQuery(query.trim()), 300);
  return () => window.clearTimeout(timer);
}, [query]);

const loadList = useCallback(async () => {
  const requestId = ++listRequestIdRef.current;
  setListLoading(true);
  try {
    const response = await videoNoteApi.list({
      knowledgeBaseId,
      q: effectiveQuery || undefined,
      includeBodySearch,
    });
    if (requestId !== listRequestIdRef.current) return;
    setWorkspaceError(null);
    setItems(response.items);
    setSelectedBvid((current) => {
      if (current || response.items.length === 0) return current;
      const preferred =
        response.items.find((item) => item.has_note) ?? response.items[0];
      return preferred.bvid;
    });
  } catch (error) {
    if (requestId !== listRequestIdRef.current) return;
    setWorkspaceError(formatWorkspaceError("无法加载视频笔记列表", error));
  } finally {
    if (requestId === listRequestIdRef.current) setListLoading(false);
  }
}, [effectiveQuery, includeBodySearch, knowledgeBaseId]);
```

When `includeBodySearch` or `knowledgeBaseId` changes, `loadList` still runs immediately because they are direct dependencies. Keep the current list while a request is pending.

- [ ] **Step 5: Run selection tests and verify GREEN**

Run `npm test -- VideoNoteWorkspace.selection.test.tsx` from `frontend`.

Expected: all selection tests PASS.

- [ ] **Step 6: Run all video-note frontend tests**

```powershell
Push-Location frontend
npm test -- components/video-notes
Pop-Location
```

Expected: all video-note test files PASS.

- [ ] **Step 7: Review and commit only Task 4 hunks**

```powershell
git diff -- frontend/components/video-notes/VideoNoteWorkspace.tsx frontend/components/video-notes/VideoNoteWorkspace.selection.test.tsx frontend/components/video-notes/VideoNoteListPanel.tsx
git add -p -- frontend/components/video-notes/VideoNoteWorkspace.tsx frontend/components/video-notes/VideoNoteWorkspace.selection.test.tsx frontend/components/video-notes/VideoNoteListPanel.tsx
git diff --cached --check
git commit -m "perf: debounce video note search"
```

If request-race hunks overlap the existing note-switch protection, defer the commit rather than stage unrelated lines.

### Task 5: Full verification and rendered QA

**Files:**

- Verify only; do not add screenshots, reports, traces, or temporary scripts to the repository.

- [ ] **Step 1: Inspect the complete worktree and intended diff**

```powershell
git status --short
git diff --check
git diff -- app/schemas/video_notes.py app/services/video_note_ai_suggestions.py app/services/video_note_markdown.py frontend/lib/api/videoNoteTypes.ts frontend/components/video-notes frontend/app/styles/video-notes
```

Expected: no whitespace errors, no secret/generated files, and no unexplained edits from this plan.

- [ ] **Step 2: Run repository formatting and full verification**

Because the worktree contains pre-existing changes, first confirm all current changes are intended before allowing `-Format` to modify them. Then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1 -Format
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-before-commit.ps1
```

Expected: Black, backend tests, Prettier, frontend lint, frontend tests, production build, and whitespace checks all PASS.

- [ ] **Step 3: Start the app for rendered QA**

Browser plugin classification: absent in this session. Prefer an existing repository Playwright workflow if discovered:

```powershell
Push-Location frontend
Get-Content -Raw package.json
npx playwright --version
Pop-Location
```

Start the existing development stack with the repository scripts and keep the configured host exact. Do not install new browser dependencies.

- [ ] **Step 4: Run desktop and mobile interaction checks**

The flow under test is: open a video note -> run AI actions -> inspect source card -> protect an existing block with confirmation -> search quickly -> observe only the final result.

At desktop and one mobile viewport, verify:

1. Page URL/title and meaningful content render.
2. No Next.js/Vite/Webpack error overlay appears.
3. Console has no relevant warning or error.
4. AI, official, and fallback cards have distinct labels; fallback has a warm warning treatment.
5. Non-empty target shows “覆盖现有内容？”; cancel makes no request; confirm applies and undo restores.
6. Timestamp text uses `03:24` and `01:02:03` where fixtures allow.
7. Rapid search produces only the final query result and the list does not roll back.

Save temporary screenshots outside the repository and include their absolute paths in the final QA report.

- [ ] **Step 5: Final status verification**

```powershell
git status --short
git log -5 --oneline
git diff --check
```

Expected: report any remaining pre-existing uncommitted changes explicitly; do not claim a clean worktree unless this output is empty.
