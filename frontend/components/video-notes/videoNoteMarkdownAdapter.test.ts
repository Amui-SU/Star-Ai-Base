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
  it("serializes timestamp outlines with adaptive time segments", () => {
    const timestampBlocks: VideoNoteBlock[] = [
      {
        id: "timestamps",
        type: "timestamp_outline",
        items: [
          { time: 204, text: "Chapter" },
          { time: 3723, text: "Long chapter" },
        ],
      },
    ];

    expect(blocksToMarkdown(timestampBlocks)).toBe(
      ["- [03:24] Chapter", "- [01:02:03] Long chapter"].join("\n"),
    );
  });

  it("normalizes invalid and fractional timestamp outline values", () => {
    const timestampBlocks = [
      {
        id: "timestamp-boundaries",
        type: "timestamp_outline",
        items: [
          { time: 204.9, text: "Fraction" },
          { time: 360000.9, text: "Long" },
          { time: "204", text: "String" },
          { time: true, text: "Boolean" },
          { time: Number.NaN, text: "NaN" },
          { time: Number.POSITIVE_INFINITY, text: "Positive infinity" },
          { time: Number.NEGATIVE_INFINITY, text: "Negative infinity" },
        ],
      },
    ] as unknown as VideoNoteBlock[];

    expect(blocksToMarkdown(timestampBlocks)).toBe(
      [
        "- [03:24] Fraction",
        "- [100:00:00] Long",
        "- [00:00] String",
        "- [00:00] Boolean",
        "- [00:00] NaN",
        "- [00:00] Positive infinity",
        "- [00:00] Negative infinity",
      ].join("\n"),
    );
  });

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

  it("parses timestamp Markdown lists without dropping item times", () => {
    const parsed = markdownToVideoNoteBlocks(
      [
        "- [00:00] 开场介绍",
        "- [01:04] 拆解核心流程",
        "- [01:02:03] 总结与行动",
      ].join("\n"),
    );

    expect(parsed).toMatchObject([
      {
        type: "timestamp_outline",
        items: [
          { time: 0, text: "开场介绍" },
          { time: 64, text: "拆解核心流程" },
          { time: 3723, text: "总结与行动" },
        ],
      },
    ]);
  });
});
