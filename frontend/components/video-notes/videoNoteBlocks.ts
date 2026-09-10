import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";

const createId = () =>
  `block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const replaceTargetAliases: Record<string, string[]> = {
  questions: ["questions", "ai-review-questions"],
  "ai-review-questions": ["questions", "ai-review-questions"],
};

export function getVideoNoteReplacementTargetIds(targetId: string): string[] {
  return replaceTargetAliases[targetId] ?? [targetId];
}

export function createVideoNoteBlock(
  type: VideoNoteBlock["type"] = "paragraph",
  values: Partial<VideoNoteBlock> = {},
): VideoNoteBlock {
  return {
    id: values.id ?? createId(),
    type,
    text: values.text ?? "",
    level: type === "heading" ? (values.level ?? 2) : values.level,
    items: values.items,
    checked: values.checked,
    source: values.source,
  };
}

export function addVideoNoteBlock(
  blocks: VideoNoteBlock[],
  block: VideoNoteBlock,
  afterId?: string,
): VideoNoteBlock[] {
  if (!afterId) return [...blocks, block];
  const index = blocks.findIndex((item) => item.id === afterId);
  if (index === -1) return [...blocks, block];
  return [...blocks.slice(0, index + 1), block, ...blocks.slice(index + 1)];
}

export function removeVideoNoteBlock(
  blocks: VideoNoteBlock[],
  blockId: string,
): VideoNoteBlock[] {
  return blocks.filter((block) => block.id !== blockId);
}

function replaceOrInsertBlock(
  blocks: VideoNoteBlock[],
  operation: VideoNoteAiOperation,
): VideoNoteBlock[] {
  if (!operation.block) return blocks;
  const targetId = operation.target_block_id ?? operation.block.id;
  const targetIds = getVideoNoteReplacementTargetIds(targetId);
  const index = blocks.findIndex((block) => targetIds.includes(block.id));
  const replacement = { ...operation.block, id: targetIds[0] };
  if (index === -1) return [...blocks, replacement];
  return blocks.reduce<VideoNoteBlock[]>((nextBlocks, block, blockIndex) => {
    if (!targetIds.includes(block.id)) {
      nextBlocks.push(block);
      return nextBlocks;
    }
    if (blockIndex === index) {
      nextBlocks.push(replacement);
    }
    return nextBlocks;
  }, []);
}

export function applyVideoNoteAiOperations(
  blocks: VideoNoteBlock[],
  operations: VideoNoteAiOperation[],
): VideoNoteBlock[] {
  return operations.reduce(
    (current, operation) => {
      if (operation.kind === "insert_block" && operation.block) {
        return [...current, operation.block];
      }
      if (operation.kind === "replace_or_insert_block") {
        return replaceOrInsertBlock(current, operation);
      }
      if (operation.kind === "replace_blocks" && operation.blocks) {
        return [...operation.blocks];
      }
      if (operation.kind === "remove_block" && operation.target_block_id) {
        return removeVideoNoteBlock(current, operation.target_block_id);
      }
      return current;
    },
    [...blocks],
  );
}
