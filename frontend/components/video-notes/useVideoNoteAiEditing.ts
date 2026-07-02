"use client";

import { useCallback, useState } from "react";

import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";
import { applyVideoNoteAiOperations } from "./videoNoteBlocks";

interface UseVideoNoteAiEditingOptions {
  blocks: VideoNoteBlock[];
  onBlocksChange: (blocks: VideoNoteBlock[]) => void;
}

export function useVideoNoteAiEditing({
  blocks,
  onBlocksChange,
}: UseVideoNoteAiEditingOptions) {
  const [undoStack, setUndoStack] = useState<VideoNoteBlock[][]>([]);

  const applyAiOperations = useCallback(
    (operations: VideoNoteAiOperation[]) => {
      const nextBlocks = applyVideoNoteAiOperations(blocks, operations);
      setUndoStack((current) => [...current, blocks]);
      onBlocksChange(nextBlocks);
    },
    [blocks, onBlocksChange],
  );

  const undoAiEdit = useCallback(() => {
    setUndoStack((current) => {
      const previous = current.at(-1);
      if (!previous) return current;
      onBlocksChange(previous);
      return current.slice(0, -1);
    });
  }, [onBlocksChange]);

  return {
    applyAiOperations,
    undoAiEdit,
    canUndoAiEdit: undoStack.length > 0,
    undoDepth: undoStack.length,
  };
}
