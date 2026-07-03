import { describe, expect, it } from "vitest";

import type { VideoNoteBlock } from "@/lib/api";
import {
  blocksToMarkdown,
  markdownToVideoNoteBlocks,
} from "./videoNoteMarkdownAdapter";

const blocks: VideoNoteBlock[] = [
  { id: "h1", type: "heading", level: 1, text: "Session Plan" },
  { id: "p1", type: "paragraph", text: "Watch the intro carefully." },
  { id: "todo1", type: "todo", text: "Review transcript", checked: false },
  {
    id: "list1",
    type: "key_points",
    items: [{ text: "First insight" }, { text: "Second insight" }],
  },
  { id: "quote1", type: "quote", text: "Quote line one\nQuote line two" },
  { id: "hr1", type: "divider" },
];

describe("video note markdown adapter", () => {
  it("serializes note blocks into editable Markdown", () => {
    expect(blocksToMarkdown(blocks)).toBe(
      [
        "# Session Plan",
        "",
        "Watch the intro carefully.",
        "",
        "- [ ] Review transcript",
        "",
        "- First insight",
        "- Second insight",
        "",
        "> Quote line one",
        "> Quote line two",
        "",
        "---",
      ].join("\n"),
    );
  });

  it("parses edited Markdown while preserving stable block ids by position", () => {
    const parsed = markdownToVideoNoteBlocks(
      ["# Updated Plan", "", "New body from Vditor."].join("\n"),
      blocks,
    );

    expect(parsed).toEqual([
      { id: "h1", type: "heading", level: 1, text: "Updated Plan" },
      { id: "p1", type: "paragraph", text: "New body from Vditor." },
    ]);
  });

  it("parses task lists, bullet lists, blockquotes, and dividers", () => {
    const parsed = markdownToVideoNoteBlocks(
      [
        "- [x] Done",
        "- [ ] Next",
        "",
        "- Key point",
        "- Another point",
        "",
        "> Keep this quote",
        "> with context",
        "",
        "---",
      ].join("\n"),
    );

    expect(parsed).toMatchObject([
      { type: "todo", text: "Done", checked: true },
      { type: "todo", text: "Next", checked: false },
      {
        type: "bulleted_list",
        items: [{ text: "Key point" }, { text: "Another point" }],
      },
      { type: "quote", text: "Keep this quote\nwith context" },
      { type: "divider" },
    ]);
    expect(parsed.every((block) => block.id)).toBe(true);
  });
});
