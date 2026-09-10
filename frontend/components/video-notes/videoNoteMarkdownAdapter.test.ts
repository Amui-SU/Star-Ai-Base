import { performance } from "node:perf_hooks";
import { describe, expect, it } from "vitest";

import type { VideoNoteBlock } from "@/lib/api";
import {
  blocksToMarkdown,
  markdownToVideoNoteBlocks,
} from "./videoNoteMarkdownAdapter";
import { getVideoNoteAiOverwriteTargets } from "./videoNoteAiUi";

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

const standardBlocks: VideoNoteBlock[] = [
  { id: "title", type: "heading", level: 1, text: "课程标题" },
  { id: "source", type: "quote", text: "来源：示例" },
  { id: "ai-summary-title", type: "heading", level: 2, text: "AI 摘要" },
  { id: "ai-summary", type: "ai_summary", text: "" },
  { id: "key-points-title", type: "heading", level: 2, text: "关键观点" },
  { id: "key-points", type: "key_points", items: [] },
  {
    id: "timestamp-title",
    type: "heading",
    level: 2,
    text: "时间戳提纲",
  },
  { id: "timestamp-outline", type: "timestamp_outline", items: [] },
  { id: "my-notes-title", type: "heading", level: 2, text: "我的笔记" },
  { id: "my-notes", type: "paragraph", text: "" },
  { id: "questions-title", type: "heading", level: 2, text: "问题与待办" },
  { id: "questions", type: "questions", items: [] },
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

  it("does not transfer empty AI content ids to following section headings", () => {
    const parsed = markdownToVideoNoteBlocks(
      blocksToMarkdown(standardBlocks),
      standardBlocks,
    );

    expect(
      parsed
        .filter((block) => block.type === "heading")
        .map((block) => block.id),
    ).toEqual([
      "title",
      "ai-summary-title",
      "key-points-title",
      "timestamp-title",
      "my-notes-title",
      "questions-title",
    ]);
    expect(
      parsed.some((block) =>
        ["ai-summary", "key-points", "timestamp-outline", "questions"].includes(
          block.id,
        ),
      ),
    ).toBe(false);
    expect(getVideoNoteAiOverwriteTargets(parsed, "summary")).toEqual([]);
  });

  it("restores stable AI ids from section headings after Markdown edits", () => {
    const markdown = [
      "# 课程标题",
      "",
      "> 来源：示例",
      "",
      "## AI 摘要",
      "",
      "用户编辑后的摘要",
      "",
      "## 关键观点",
      "",
      "- 观点一",
      "",
      "## 时间戳提纲",
      "",
      "- [00:24] 开场",
      "",
      "## 我的笔记",
      "",
      "普通笔记",
      "",
      "## 问题与待办",
      "",
      "- 如何复述？",
    ].join("\n");

    const parsed = markdownToVideoNoteBlocks(markdown, standardBlocks);

    expect(parsed.find((block) => block.id === "ai-summary")).toMatchObject({
      type: "paragraph",
      text: "用户编辑后的摘要",
    });
    expect(parsed.find((block) => block.id === "key-points")).toMatchObject({
      type: "bulleted_list",
      items: [{ text: "观点一" }],
    });
    expect(
      parsed.find((block) => block.id === "timestamp-outline"),
    ).toMatchObject({ items: [{ time: 24, text: "开场" }] });
    expect(parsed.find((block) => block.id === "questions")).toMatchObject({
      type: "bulleted_list",
      items: [{ text: "如何复述？" }],
    });
    expect(getVideoNoteAiOverwriteTargets(parsed, "summary")).toEqual([
      "摘要",
      "关键观点",
    ]);
    expect(getVideoNoteAiOverwriteTargets(parsed, "questions")).toEqual([
      "复盘问题",
    ]);
    expect(getVideoNoteAiOverwriteTargets(parsed, "timestamps")).toEqual([
      "时间戳提纲",
    ]);
  });

  it("keeps semantic ids stable when ordinary paragraphs are inserted or deleted", () => {
    const previousBlocks: VideoNoteBlock[] = [
      standardBlocks[0],
      { id: "intro-keep", type: "paragraph", text: "保留段落" },
      { id: "intro-remove", type: "paragraph", text: "删除段落" },
      ...standardBlocks.slice(1, 3),
      { ...standardBlocks[3], text: "原摘要" },
      ...standardBlocks.slice(4),
    ];
    const markdown = blocksToMarkdown(previousBlocks)
      .replace("删除段落\n\n", "")
      .replace("## AI 摘要", "新增段落\n\n## AI 摘要")
      .replace("原摘要", "编辑后的摘要");

    const parsed = markdownToVideoNoteBlocks(markdown, previousBlocks);
    const headings = parsed.filter((block) => block.type === "heading");

    expect(parsed.find((block) => block.id === "intro-keep")?.text).toBe(
      "保留段落",
    );
    expect(parsed.find((block) => block.id === "ai-summary")?.text).toBe(
      "编辑后的摘要",
    );
    expect(headings.find((block) => block.text === "AI 摘要")?.id).toBe(
      "ai-summary-title",
    );
    expect(
      headings.some((block) =>
        ["ai-summary", "key-points", "timestamp-outline", "questions"].includes(
          block.id,
        ),
      ),
    ).toBe(false);
  });

  it("prioritizes semantic ids when an ordinary block moves before its section", () => {
    const previousBlocks: VideoNoteBlock[] = [
      {
        id: "ai-summary-title",
        type: "heading",
        level: 2,
        text: standardBlocks[2].text,
      },
      { id: "ai-summary", type: "ai_summary", text: "Original summary" },
      { id: "ordinary", type: "paragraph", text: "Ordinary paragraph" },
    ];

    const parsed = markdownToVideoNoteBlocks(
      [
        "Ordinary paragraph",
        "",
        `## ${standardBlocks[2].text}`,
        "",
        "Original summary",
      ].join("\n"),
      previousBlocks,
    );

    expect(parsed[1].id).toBe("ai-summary-title");
    expect(parsed[2].id).toBe("ai-summary");
    expect(parsed[0].id).not.toBe("ordinary");
  });

  it("preserves an edited block id between anchors after an earlier insertion", () => {
    const previousBlocks: VideoNoteBlock[] = [
      { id: "anchor-a", type: "paragraph", text: "Anchor A" },
      { id: "edited", type: "paragraph", text: "Original text" },
      { id: "anchor-z", type: "paragraph", text: "Anchor Z" },
    ];

    const parsed = markdownToVideoNoteBlocks(
      ["Inserted", "", "Anchor A", "", "Edited text", "", "Anchor Z"].join(
        "\n",
      ),
      previousBlocks,
    );

    expect(parsed.find((block) => block.text === "Edited text")?.id).toBe(
      "edited",
    );
    expect(parsed.find((block) => block.text === "Inserted")?.id).not.toBe(
      "edited",
    );
  });

  it("preserves an edited block id between anchors after an earlier deletion", () => {
    const previousBlocks: VideoNoteBlock[] = [
      { id: "removed", type: "paragraph", text: "Removed" },
      { id: "anchor-a", type: "paragraph", text: "Anchor A" },
      { id: "edited", type: "paragraph", text: "Original text" },
      { id: "anchor-z", type: "paragraph", text: "Anchor Z" },
    ];

    const parsed = markdownToVideoNoteBlocks(
      ["Anchor A", "", "Edited text", "", "Anchor Z"].join("\n"),
      previousBlocks,
    );

    expect(parsed.find((block) => block.text === "Edited text")?.id).toBe(
      "edited",
    );
  });

  it("does not guess a substituted block id during bidirectional structural edits", () => {
    const previousBlocks: VideoNoteBlock[] = [
      { id: "removed", type: "paragraph", text: "Removed" },
      { id: "anchor-a", type: "paragraph", text: "Anchor A" },
      { id: "anchor-b", type: "paragraph", text: "Anchor B" },
      { id: "old-substitution", type: "paragraph", text: "Old candidate" },
      { id: "anchor-z", type: "paragraph", text: "Anchor Z" },
    ];

    const parsed = markdownToVideoNoteBlocks(
      [
        "Anchor A",
        "",
        "Inserted",
        "",
        "Anchor B",
        "",
        "Replacement",
        "",
        "Anchor Z",
      ].join("\n"),
      previousBlocks,
    );

    expect(parsed.find((block) => block.text === "Replacement")?.id).not.toBe(
      "old-substitution",
    );
  });

  it.each([
    {
      position: "before",
      markdown: [
        "# 课程标题",
        "",
        "## AI 摘要",
        "",
        "新增的同名区块",
        "",
        "## AI 摘要",
        "",
        "原摘要",
        "",
        "## 关键观点",
        "",
        "- 原观点",
      ].join("\n"),
    },
    {
      position: "after",
      markdown: [
        "# 课程标题",
        "",
        "## AI 摘要",
        "",
        "原摘要",
        "",
        "## AI 摘要",
        "",
        "新增的同名区块",
        "",
        "## 关键观点",
        "",
        "- 原观点",
      ].join("\n"),
    },
  ])(
    "keeps semantic ids on the original section when a duplicate is inserted $position it",
    ({ markdown }) => {
      const previousBlocks: VideoNoteBlock[] = [
        { id: "title", type: "heading", level: 1, text: "课程标题" },
        {
          id: "ai-summary-title",
          type: "heading",
          level: 2,
          text: "AI 摘要",
        },
        { id: "ai-summary", type: "ai_summary", text: "原摘要" },
        {
          id: "key-points-title",
          type: "heading",
          level: 2,
          text: "关键观点",
        },
        {
          id: "key-points",
          type: "key_points",
          items: [{ text: "原观点" }],
        },
      ];

      const parsed = markdownToVideoNoteBlocks(markdown, previousBlocks);
      const originalHeadingIndex = parsed.findIndex(
        (block, index) =>
          block.type === "heading" &&
          block.text === "AI 摘要" &&
          parsed[index + 1]?.text === "原摘要",
      );
      const duplicateHeadingIndex = parsed.findIndex(
        (block, index) =>
          block.type === "heading" &&
          block.text === "AI 摘要" &&
          parsed[index + 1]?.text === "新增的同名区块",
      );

      expect(parsed[originalHeadingIndex].id).toBe("ai-summary-title");
      expect(parsed[originalHeadingIndex + 1].id).toBe("ai-summary");
      expect(parsed[duplicateHeadingIndex].id).not.toBe("ai-summary-title");
      expect(parsed[duplicateHeadingIndex + 1].id).not.toBe("ai-summary");
    },
  );

  it("does not guess a semantic id when duplicate sections are indistinguishable", () => {
    const previousBlocks: VideoNoteBlock[] = [
      {
        id: "ai-summary-title",
        type: "heading",
        level: 2,
        text: "AI 摘要",
      },
      { id: "ai-summary", type: "ai_summary", text: "相同摘要" },
    ];
    const parsed = markdownToVideoNoteBlocks(
      ["## AI 摘要", "", "相同摘要", "", "## AI 摘要", "", "相同摘要"].join(
        "\n",
      ),
      previousBlocks,
    );

    expect(parsed.some((block) => block.id === "ai-summary-title")).toBe(false);
    expect(parsed.some((block) => block.id === "ai-summary")).toBe(false);
  });

  it("does not inherit arbitrary ids for indistinguishable ordinary paragraphs", () => {
    const previousBlocks: VideoNoteBlock[] = [
      { id: "old-left", type: "paragraph", text: "Unique left anchor" },
      { id: "old-repeat-1", type: "paragraph", text: "Repeated paragraph" },
      { id: "old-repeat-2", type: "paragraph", text: "Repeated paragraph" },
      { id: "old-repeat-3", type: "paragraph", text: "Repeated paragraph" },
      { id: "old-right", type: "paragraph", text: "Unique right anchor" },
    ];

    const parsed = markdownToVideoNoteBlocks(
      blocksToMarkdown(previousBlocks),
      previousBlocks,
    );

    expect(parsed[0].id).toBe("old-left");
    expect(parsed.at(-1)?.id).toBe("old-right");
    expect(
      parsed
        .slice(1, -1)
        .map((block) => block.id)
        .filter((id) => id.startsWith("old-repeat-")),
    ).toEqual([]);
  });

  it("reconciles 3000 edited blocks with a median duration under 50ms", () => {
    const previousBlocks: VideoNoteBlock[] = Array.from(
      { length: 3000 },
      (_, index) => ({
        id: `old-paragraph-${index + 1}`,
        type: "paragraph",
        text: `Unique paragraph ${index + 1}`,
      }),
    );
    const editedBlocks: VideoNoteBlock[] = [];

    previousBlocks.forEach((block, index) => {
      const position = index + 1;
      if (position % 31 === 0) {
        editedBlocks.push({
          id: `inserted-paragraph-${position}`,
          type: "paragraph",
          text: `Unique inserted paragraph ${position}`,
        });
      }
      if (position % 17 !== 0) editedBlocks.push(block);
    });

    const markdown = blocksToMarkdown(editedBlocks);
    const warmupResult = markdownToVideoNoteBlocks(markdown, previousBlocks);
    const warmupBlockByText = new Map(
      warmupResult.map((block) => [block.text, block]),
    );

    expect.soft(warmupResult).toHaveLength(editedBlocks.length);
    expect
      .soft(warmupResult.map((block) => block.text))
      .toEqual(editedBlocks.map((block) => block.text));
    [1, 1500, 3000].forEach((position) => {
      const previousBlock = previousBlocks[position - 1];
      expect
        .soft(warmupBlockByText.get(previousBlock.text)?.id)
        .toBe(previousBlock.id);
    });
    const previousIds = new Set(previousBlocks.map((block) => block.id));
    const insertedBlocksWithOldIds = editedBlocks
      .filter((block) => block.id.startsWith("inserted-paragraph-"))
      .flatMap((insertedBlock) => {
        const reconciledBlock = warmupBlockByText.get(insertedBlock.text);
        return reconciledBlock && previousIds.has(reconciledBlock.id)
          ? [{ text: reconciledBlock.text, id: reconciledBlock.id }]
          : [];
      });
    expect.soft(insertedBlocksWithOldIds).toEqual([]);

    const durations = Array.from({ length: 5 }, () => {
      const startedAt = performance.now();
      markdownToVideoNoteBlocks(markdown, previousBlocks);
      return performance.now() - startedAt;
    });
    const sortedDurations = [...durations].sort((left, right) => left - right);
    const medianDuration =
      sortedDurations[Math.floor(sortedDurations.length / 2)];

    expect(
      medianDuration,
      `durations: ${durations.map((duration) => `${duration.toFixed(2)}ms`).join(", ")}`,
    ).toBeLessThan(50);
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
