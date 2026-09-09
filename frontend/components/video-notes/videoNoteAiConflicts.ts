import type { VideoNoteAiOperation, VideoNoteBlock } from "@/lib/api";
import { getVideoNoteReplacementTargetIds } from "./videoNoteBlocks";

function fingerprint(blocks: VideoNoteBlock[]): string {
  return JSON.stringify(
    blocks.map((block) => [
      block.id,
      block.type,
      block.text,
      block.level,
      block.checked,
      block.source,
      block.items?.map((item) => [
        item.text,
        item.content,
        item.time,
        item.timestamp,
        item.checked,
      ]),
    ]),
  );
}

/** Compare only content the response can overwrite, including legacy aliases. */
export function hasVideoNoteAiConflict(
  starting: VideoNoteBlock[],
  current: VideoNoteBlock[],
  operations: VideoNoteAiOperation[],
): boolean {
  return operations.some((operation) => {
    if (operation.kind === "replace_blocks" && operation.blocks) {
      return fingerprint(starting) !== fingerprint(current);
    }
    if (operation.kind === "insert_block" && operation.block) {
      return current.some((block) => block.id === operation.block?.id);
    }
    let ids: string[] = [];
    if (operation.kind === "replace_or_insert_block" && operation.block) {
      ids = getVideoNoteReplacementTargetIds(
        operation.target_block_id ?? operation.block.id,
      );
    } else if (operation.kind === "remove_block" && operation.target_block_id) {
      ids = [operation.target_block_id];
    }
    return (
      fingerprint(starting.filter((block) => ids.includes(block.id))) !==
      fingerprint(current.filter((block) => ids.includes(block.id)))
    );
  });
}
