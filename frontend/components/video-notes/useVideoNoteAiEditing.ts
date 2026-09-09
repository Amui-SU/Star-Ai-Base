"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";

import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";
import { applyVideoNoteAiOperations } from "./videoNoteBlocks";
import { hasVideoNoteAiConflict } from "./videoNoteAiConflicts";

interface UseVideoNoteAiEditingOptions {
  blocks: VideoNoteBlock[];
  onBlocksChange: (blocks: VideoNoteBlock[]) => void;
}

export function useVideoNoteAiEditing({
  blocks,
  onBlocksChange,
}: UseVideoNoteAiEditingOptions) {
  const [undoStack, setUndoStack] = useState<VideoNoteBlock[][]>([]);
  const latest = useRef({ blocks, onBlocksChange });
  useLayoutEffect(() => {
    latest.current = { blocks, onBlocksChange };
  }, [blocks, onBlocksChange]);

  const applyAiOperations = useCallback(
    (
      operations: VideoNoteAiOperation[],
      startingBlocks: VideoNoteBlock[] = blocks,
    ) => {
      const currentBlocks = latest.current.blocks;
      if (hasVideoNoteAiConflict(startingBlocks, currentBlocks, operations))
        return false;
      const nextBlocks = applyVideoNoteAiOperations(currentBlocks, operations);
      setUndoStack((current) => [...current, currentBlocks]);
      latest.current.blocks = nextBlocks;
      latest.current.onBlocksChange(nextBlocks);
      return true;
    },
    [blocks],
  );

  const undoAiEdit = useCallback(() => {
    setUndoStack((current) => {
      const previous = current.at(-1);
      if (!previous) return current;
      onBlocksChange(previous);
      return current.slice(0, -1);
    });
  }, [onBlocksChange]);

  // 切换视频时必须清空撤销栈，否则会把上一个视频的内容灌进当前笔记
  const resetAiEditing = useCallback(() => {
    setUndoStack([]);
  }, []);

  return {
    applyAiOperations,
    undoAiEdit,
    resetAiEditing,
    canUndoAiEdit: undoStack.length > 0,
    undoDepth: undoStack.length,
  };
}
