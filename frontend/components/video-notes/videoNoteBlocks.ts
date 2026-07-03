import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";

const createId = () =>
  `block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const replaceTargetAliases: Record<string, string[]> = {
  questions: ["questions", "ai-review-questions"],
  "ai-review-questions": ["questions", "ai-review-questions"],
};

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

export function updateVideoNoteBlock(
  blocks: VideoNoteBlock[],
  blockId: string,
  patch: Partial<VideoNoteBlock>,
): VideoNoteBlock[] {
  return blocks.map((block) =>
    block.id === blockId ? { ...block, ...patch, id: block.id } : block,
  );
}

export function removeVideoNoteBlock(
  blocks: VideoNoteBlock[],
  blockId: string,
): VideoNoteBlock[] {
  return blocks.filter((block) => block.id !== blockId);
}

export function moveVideoNoteBlock(
  blocks: VideoNoteBlock[],
  blockId: string,
  direction: "up" | "down",
): VideoNoteBlock[] {
  const index = blocks.findIndex((block) => block.id === blockId);
  const nextIndex = direction === "up" ? index - 1 : index + 1;
  if (index < 0 || nextIndex < 0 || nextIndex >= blocks.length) {
    return blocks;
  }
  const next = [...blocks];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

export function convertVideoNoteBlock(
  blocks: VideoNoteBlock[],
  blockId: string,
  type: VideoNoteBlock["type"],
): VideoNoteBlock[] {
  return blocks.map((block) => {
    if (block.id !== blockId) return block;
    const converted: VideoNoteBlock = {
      id: block.id,
      type,
      text: block.text ?? "",
    };
    if (type === "heading") converted.level = block.level ?? 2;
    if (type === "todo") converted.checked = Boolean(block.checked);
    if (
      [
        "key_points",
        "questions",
        "timestamp_outline",
        "bulleted_list",
      ].includes(type)
    ) {
      converted.items = block.items ?? [];
    }
    return converted;
  });
}

function textFromItem(item: unknown): string {
  if (!item || typeof item !== "object") return "";
  const record = item as { text?: unknown; content?: unknown };
  return String(record.text ?? record.content ?? "").trim();
}

export function extractVideoNotePlainText(block: VideoNoteBlock): string {
  const text = String(block.text ?? "").trim();
  const items = (block.items ?? []).map(textFromItem).filter(Boolean);
  return [text, ...items].filter(Boolean).join(" ");
}

export function extractVideoNoteSearchText(blocks: VideoNoteBlock[]): string {
  return blocks.map(extractVideoNotePlainText).filter(Boolean).join(" ");
}

function replaceOrInsertBlock(
  blocks: VideoNoteBlock[],
  operation: VideoNoteAiOperation,
): VideoNoteBlock[] {
  if (!operation.block) return blocks;
  const targetId = operation.target_block_id ?? operation.block.id;
  const targetIds = replaceTargetAliases[targetId] ?? [targetId];
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
