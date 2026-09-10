import { expect, it } from "vitest";
import type { VideoNoteBlock } from "@/lib/api";
import { hasVideoNoteAiConflict } from "./videoNoteAiConflicts";

it("accepts unchanged content regardless of object property order", () => {
  const before: VideoNoteBlock[] = [
    { id: "p", type: "paragraph", text: "same" },
  ];
  const after: VideoNoteBlock[] = [
    { text: "same", type: "paragraph", id: "p" },
  ];
  expect(
    hasVideoNoteAiConflict(before, after, [
      { kind: "replace_blocks", blocks: [] },
    ]),
  ).toBe(false);
});

it("allows replacing unchanged legacy questions while preserving an unrelated edit", () => {
  const questions: VideoNoteBlock = {
    id: "ai-review-questions",
    type: "questions",
    items: [{ text: "Q?" }],
  };
  expect(
    hasVideoNoteAiConflict(
      [questions],
      [questions, { id: "new", type: "paragraph", text: "manual" }],
      [
        {
          kind: "replace_or_insert_block",
          target_block_id: "questions",
          block: {
            id: "questions",
            type: "questions",
            items: [{ text: "new Q?" }],
          },
        },
      ],
    ),
  ).toBe(false);
});

it("rejects the whole response if any operation targets a changed nested item", () => {
  const before: VideoNoteBlock[] = [
    { id: "todo", type: "todo", items: [{ text: "review", checked: false }] },
  ];
  const after: VideoNoteBlock[] = [
    { ...before[0], items: [{ text: "review", checked: true }] },
  ];
  expect(
    hasVideoNoteAiConflict(before, after, [
      {
        kind: "insert_block",
        block: { id: "new", type: "paragraph", text: "AI" },
      },
      { kind: "remove_block", target_block_id: "todo" },
    ]),
  ).toBe(true);
});
