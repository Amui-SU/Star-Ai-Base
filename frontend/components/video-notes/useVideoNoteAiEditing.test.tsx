import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useVideoNoteAiEditing } from "./useVideoNoteAiEditing";
import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";

describe("useVideoNoteAiEditing", () => {
  const starting: VideoNoteBlock[] = [
    { id: "p1", type: "paragraph", text: "target" },
    { id: "p2", type: "paragraph", text: "unrelated" },
  ];
  const replacement: VideoNoteAiOperation = {
    kind: "replace_or_insert_block",
    target_block_id: "p1",
    block: { id: "p1", type: "ai_summary", text: "AI" },
  };

  it("preserves unrelated edits and latest callback when an old request finishes, including undo", () => {
    const originalChange = vi.fn();
    const latestChange = vi.fn();
    const { result, rerender } = renderHook(
      (props) => useVideoNoteAiEditing(props),
      { initialProps: { blocks: starting, onBlocksChange: originalChange } },
    );
    const applyFromRequest = result.current.applyAiOperations;
    const current = [starting[0], { ...starting[1], text: "manual edit" }];
    rerender({ blocks: current, onBlocksChange: latestChange });
    act(() => {
      applyFromRequest([replacement], starting);
    });
    expect(originalChange).not.toHaveBeenCalled();
    expect(latestChange).toHaveBeenLastCalledWith([
      { id: "p1", type: "ai_summary", text: "AI" },
      current[1],
    ]);
    act(() => result.current.undoAiEdit());
    expect(latestChange).toHaveBeenLastCalledWith(current);
  });

  it.each([
    {
      name: "changed target",
      current: [{ ...starting[0], text: "manual" }, starting[1]],
      operation: replacement,
    },
    { name: "removed target", current: [starting[1]], operation: replacement },
    {
      name: "remove changed target",
      current: [{ ...starting[0], text: "manual" }],
      operation: { kind: "remove_block", target_block_id: "p1" },
    },
    {
      name: "replace document after edit",
      current: [starting[0], { ...starting[1], text: "manual" }],
      operation: { kind: "replace_blocks", blocks: [] },
    },
    {
      name: "insert existing ID",
      current: starting,
      operation: { kind: "insert_block", block: starting[0] },
    },
    {
      name: "changed legacy questions alias",
      current: [
        {
          id: "ai-review-questions",
          type: "questions",
          items: [{ text: "manual" }],
        },
      ],
      operation: {
        kind: "replace_or_insert_block",
        target_block_id: "questions",
        block: { id: "questions", type: "questions", items: [] },
      },
    },
  ] as {
    name: string;
    current: VideoNoteBlock[];
    operation: VideoNoteAiOperation;
  }[])("rejects $name without undo history", ({ current, operation }) => {
    const onBlocksChange = vi.fn();
    const { result, rerender } = renderHook(
      ({ blocks }) => useVideoNoteAiEditing({ blocks, onBlocksChange }),
      { initialProps: { blocks: starting } },
    );
    rerender({ blocks: current });
    act(() => {
      expect(result.current.applyAiOperations([operation], starting)).toBe(
        false,
      );
    });
    expect(onBlocksChange).not.toHaveBeenCalled();
    expect(result.current.undoDepth).toBe(0);
  });

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

  it("resetAiEditing clears all AI edit history so undo cannot leak old blocks", () => {
    const initialBlocks: VideoNoteBlock[] = [
      { id: "p1", type: "paragraph", text: "原文" },
    ];
    const onBlocksChange = vi.fn();

    const { result } = renderHook(
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
    expect(result.current.canUndoAiEdit).toBe(true);

    act(() => result.current.resetAiEditing());

    expect(result.current.canUndoAiEdit).toBe(false);
    expect(result.current.undoDepth).toBe(0);
    onBlocksChange.mockClear();
    act(() => result.current.undoAiEdit());
    expect(onBlocksChange).not.toHaveBeenCalled();
  });
});
