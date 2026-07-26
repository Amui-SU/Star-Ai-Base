import { describe, expect, it } from "vitest";

import {
  addVideoNoteBlock,
  applyVideoNoteAiOperations,
  removeVideoNoteBlock,
} from "./videoNoteBlocks";
import type { VideoNoteBlock } from "@/lib/api";

const blocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "标题" },
  { id: "p1", type: "paragraph", text: "正文" },
  { id: "todo1", type: "todo", text: "复习", checked: false },
];

describe("video note block helpers", () => {
  it("adds and removes blocks without mutating input", () => {
    const added = addVideoNoteBlock(blocks, {
      id: "p2",
      type: "paragraph",
      text: "新增",
    });
    expect(added.map((block) => block.id)).toEqual(["h1", "p1", "todo1", "p2"]);
    expect(blocks).toHaveLength(3);

    const removed = removeVideoNoteBlock(added, "todo1");
    expect(removed.map((block) => block.id)).toEqual(["h1", "p1", "p2"]);
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

    expect(next.map((block) => block.id)).toEqual(["h1", "questions", "p1"]);
    expect(next[1].items).toEqual([{ text: "新问题" }]);
  });

  it("replaces the standard questions block and removes legacy AI question blocks", () => {
    const mixedQuestionBlocks: VideoNoteBlock[] = [
      blocks[0],
      {
        id: "questions",
        type: "questions",
        items: [{ text: "标准旧问题" }],
      },
      blocks[1],
      {
        id: "ai-review-questions",
        type: "questions",
        items: [{ text: "旧版 AI 问题" }],
      },
    ];

    const next = applyVideoNoteAiOperations(mixedQuestionBlocks, [
      {
        kind: "replace_or_insert_block",
        target_block_id: "questions",
        block: {
          id: "questions",
          type: "questions",
          items: [{ text: "新的复盘问题" }],
        },
      },
    ]);

    expect(next.map((block) => block.id)).toEqual(["h1", "questions", "p1"]);
    expect(next[1].items).toEqual([{ text: "新的复盘问题" }]);
  });
});
