import { describe, expect, it } from "vitest";

import {
  addVideoNoteBlock,
  applyVideoNoteAiOperations,
  convertVideoNoteBlock,
  extractVideoNoteSearchText,
  moveVideoNoteBlock,
  removeVideoNoteBlock,
  updateVideoNoteBlock,
} from "./videoNoteBlocks";
import type { VideoNoteBlock } from "@/lib/api";

const blocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "标题" },
  { id: "p1", type: "paragraph", text: "正文" },
  { id: "todo1", type: "todo", text: "复习", checked: false },
];

describe("video note block helpers", () => {
  it("adds, updates, removes, and moves blocks without mutating input", () => {
    const added = addVideoNoteBlock(blocks, {
      id: "p2",
      type: "paragraph",
      text: "新增",
    });
    expect(added.map((block) => block.id)).toEqual(["h1", "p1", "todo1", "p2"]);
    expect(blocks).toHaveLength(3);

    const updated = updateVideoNoteBlock(added, "p1", { text: "改写正文" });
    expect(updated.find((block) => block.id === "p1")?.text).toBe("改写正文");
    expect(added.find((block) => block.id === "p1")?.text).toBe("正文");

    const moved = moveVideoNoteBlock(updated, "p2", "up");
    expect(moved.map((block) => block.id)).toEqual(["h1", "p1", "p2", "todo1"]);

    const removed = removeVideoNoteBlock(moved, "todo1");
    expect(removed.map((block) => block.id)).toEqual(["h1", "p1", "p2"]);
  });

  it("converts blocks and extracts searchable text from mixed block shapes", () => {
    const converted = convertVideoNoteBlock(blocks, "todo1", "paragraph");
    expect(converted.find((block) => block.id === "todo1")).toMatchObject({
      type: "paragraph",
      text: "复习",
    });

    expect(
      extractVideoNoteSearchText([
        ...blocks,
        {
          id: "ts",
          type: "timestamp_outline",
          items: [{ time: 12, text: "开场" }],
        },
        { id: "kp", type: "key_points", items: [{ text: "关键观点" }] },
      ]),
    ).toContain("标题 正文 复习 开场 关键观点");
  });

  it("applies AI operations with replace-or-insert semantics", () => {
    const next = applyVideoNoteAiOperations(blocks, [
      {
        kind: "replace_or_insert_block",
        target_block_id: "p1",
        block: { id: "p1", type: "ai_summary", text: "摘要" },
      },
      {
        kind: "insert_block",
        block: { id: "q1", type: "questions", items: [{ text: "问题" }] },
      },
    ]);

    expect(next.map((block) => block.id)).toEqual(["h1", "p1", "todo1", "q1"]);
    expect(next[1]).toMatchObject({ type: "ai_summary", text: "摘要" });
  });

  it("collapses duplicate generated AI blocks when replacing by target id", () => {
    const duplicatedBlocks: VideoNoteBlock[] = [
      blocks[0],
      {
        id: "ai-review-questions",
        type: "questions",
        items: [{ text: "旧问题 1" }],
      },
      blocks[1],
      {
        id: "ai-review-questions",
        type: "questions",
        items: [{ text: "旧问题 2" }],
      },
    ];

    const next = applyVideoNoteAiOperations(duplicatedBlocks, [
      {
        kind: "replace_or_insert_block",
        target_block_id: "ai-review-questions",
        block: {
          id: "ai-review-questions",
          type: "questions",
          items: [{ text: "新问题" }],
        },
      },
    ]);

    expect(next.map((block) => block.id)).toEqual([
      "h1",
      "ai-review-questions",
      "p1",
    ]);
    expect(next[1].items).toEqual([{ text: "新问题" }]);
  });
});
