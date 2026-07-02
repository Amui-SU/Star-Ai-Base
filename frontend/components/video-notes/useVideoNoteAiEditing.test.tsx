import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useVideoNoteAiEditing } from "./useVideoNoteAiEditing";
import type { VideoNoteBlock } from "@/lib/api";

describe("useVideoNoteAiEditing", () => {
  it("applies AI operations and exposes a visible undo path", () => {
    const initialBlocks: VideoNoteBlock[] = [
      { id: "p1", type: "paragraph", text: "原文" },
    ];
    const onBlocksChange = vi.fn();

    const { result, rerender } = renderHook(
      ({ blocks }) =>
        useVideoNoteAiEditing({
          blocks,
          onBlocksChange,
        }),
      { initialProps: { blocks: initialBlocks } },
    );

    act(() => {
      result.current.applyAiOperations([
        {
          kind: "replace_or_insert_block",
          target_block_id: "p1",
          block: { id: "p1", type: "ai_summary", text: "AI 摘要" },
        },
      ]);
    });

    const aiBlocks = onBlocksChange.mock.calls[0][0] as VideoNoteBlock[];
    expect(aiBlocks[0]).toMatchObject({ type: "ai_summary", text: "AI 摘要" });
    expect(result.current.canUndoAiEdit).toBe(true);

    rerender({ blocks: aiBlocks });
    act(() => result.current.undoAiEdit());

    expect(onBlocksChange.mock.calls[1][0]).toEqual(initialBlocks);
  });
});
