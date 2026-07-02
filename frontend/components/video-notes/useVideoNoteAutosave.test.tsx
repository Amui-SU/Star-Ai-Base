import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useVideoNoteAutosave } from "./useVideoNoteAutosave";
import type { VideoNote, VideoNoteBlock } from "@/lib/api";

const note: VideoNote = {
  id: 9,
  user_id: 1,
  workspace_id: 1,
  knowledge_base_id: 7,
  bvid: "BVNOTE123",
  title: "原笔记",
  template_id: "blank",
  blocks: [],
  tags: [],
  summary_status: "not_generated",
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  video: null,
};

afterEach(() => {
  vi.useRealTimers();
});

describe("useVideoNoteAutosave", () => {
  it("debounces saves and reports status", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue({ ...note, title: "新标题" });
    const blocks: VideoNoteBlock[] = [
      { id: "p1", type: "paragraph", text: "正文" },
    ];

    const { result, rerender } = renderHook(
      ({ title, currentBlocks, currentTags }) =>
        useVideoNoteAutosave({
          note,
          title,
          blocks: currentBlocks,
          tags: currentTags,
          save,
          delayMs: 200,
        }),
      { initialProps: { title: "原笔记", currentBlocks: [], currentTags: [] } },
    );

    expect(result.current.status).toBe("idle");

    rerender({ title: "新标题", currentBlocks: blocks, currentTags: ["AI"] });
    expect(result.current.status).toBe("dirty");
    expect(save).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(9, {
      title: "新标题",
      blocks,
      tags: ["AI"],
      export_filename_template: undefined,
    });
    expect(result.current.status).toBe("saved");
  });

  it("can flush pending changes immediately", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue(note);
    const { result, rerender } = renderHook(
      ({ title }) =>
        useVideoNoteAutosave({
          note,
          title,
          blocks: [],
          tags: [],
          save,
          delayMs: 500,
        }),
      { initialProps: { title: "原笔记" } },
    );

    rerender({ title: "立即保存" });
    await act(async () => {
      await result.current.flush();
    });

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(9, {
      title: "立即保存",
      blocks: [],
      tags: [],
      export_filename_template: undefined,
    });
  });
});
