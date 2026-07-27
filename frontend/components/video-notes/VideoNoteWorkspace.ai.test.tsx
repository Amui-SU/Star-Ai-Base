import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import {
  baseNote,
  findMarkdownEditor,
  renderWorkspace,
  video,
  videoNoteApi,
} from "./VideoNoteWorkspace.test-utils";

it("collapses and restores the right AI tools without removing editor tools", async () => {
  const user = userEvent.setup();
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: "BVNOTE123",
        title: "AI 视频学习法",
        has_note: true,
        note_id: 9,
        summary_status: "seeded",
        tags: ["AI"],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  const { container } = renderWorkspace({ initialBvid: "BVNOTE123" });

  await findMarkdownEditor();

  const sidePanel = container.querySelector(".video-note-side-panel");
  const drawer = container.querySelector(".video-note-drawer");
  expect(drawer).not.toHaveClass("ai-collapsed");
  expect(sidePanel).not.toHaveClass("collapsed");
  const toolRail = container.querySelector(
    ".video-note-tool-rail",
  ) as HTMLElement;
  const sideCollapseButton = within(sidePanel as HTMLElement).getByRole(
    "button",
    {
      name: "折叠 AI 工具",
    },
  );
  expect(sideCollapseButton).toBeVisible();
  expect(sideCollapseButton.querySelector("svg")).not.toBeNull();
  expect(
    within(toolRail).getByRole("button", { name: "折叠 AI 工具" }),
  ).toBeVisible();
  expect(
    within(toolRail).getByRole("button", { name: "导出 Markdown" }),
  ).toBeVisible();
  expect(within(toolRail).getAllByRole("button")[2]).toHaveAccessibleName(
    "折叠 AI 工具",
  );

  await user.click(
    within(sidePanel as HTMLElement).getByRole("button", {
      name: "折叠 AI 工具",
    }),
  );
  expect(drawer).toHaveClass("ai-collapsed");
  expect(sidePanel).toHaveClass("collapsed");
  expect(screen.queryByRole("button", { name: "生成摘要" })).toBeNull();
  expect(within(toolRail).getAllByRole("button")[2]).toHaveAccessibleName(
    "展开 AI 工具",
  );

  await user.click(
    within(toolRail).getByRole("button", { name: "展开 AI 工具" }),
  );
  expect(sidePanel).not.toHaveClass("collapsed");
  expect(drawer).not.toHaveClass("ai-collapsed");
  expect(screen.getByRole("button", { name: "生成摘要" })).toBeVisible();
});

it("applies AI suggestions with status, timestamp generation, and undo", async () => {
  const user = userEvent.setup();
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: "BVNOTE123",
        title: "AI 视频学习法",
        has_note: true,
        note_id: 9,
        summary_status: "seeded",
        tags: ["AI"],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });
  vi.mocked(videoNoteApi.generateSummary).mockResolvedValue({
    message: "已应用摘要",
    tag_suggestions: ["学习"],
    result_source: "ai",
    operations: [
      {
        kind: "replace_or_insert_block",
        target_block_id: "p1",
        block: { id: "p1", type: "ai_summary", text: "AI 新摘要" },
      },
    ],
  });
  vi.mocked(videoNoteApi.aiEdit).mockImplementation(
    async (_noteId, payload) => {
      if (payload.action === "generate_timestamps") {
        return {
          message: "已重新生成时间戳提纲",
          tag_suggestions: [],
          result_source: "official",
          operations: [
            {
              kind: "replace_or_insert_block",
              target_block_id: "timestamp-outline",
              block: {
                id: "timestamp-outline",
                type: "timestamp_outline",
                items: [{ time: 24, text: "开场目标" }],
              },
            },
          ],
        };
      }
      return {
        message: "已重新生成复盘问题",
        tag_suggestions: [],
        result_source: "fallback",
        operations: [
          {
            kind: "replace_or_insert_block",
            target_block_id: "ai-review-questions",
            block: {
              id: "ai-review-questions",
              type: "questions",
              items: [{ text: "如何复述学习目标？" }],
            },
          },
        ],
      };
    },
  );

  renderWorkspace({ initialBvid: "BVNOTE123" });

  await user.click(await screen.findByRole("button", { name: "生成摘要" }));
  const status = await screen.findByRole("status");
  expect(status).toHaveTextContent("已应用摘要");
  expect(status.closest(".video-note-ai-result-card")).toHaveTextContent(
    "AI 生成",
  );
  expect(status.closest(".video-note-ai-result-card")).toHaveTextContent(
    "由 AI 模型生成",
  );
  expect(status.closest(".video-note-ai-status-wrap")).not.toBeNull();
  expect((await findMarkdownEditor()).value).toContain("AI 新摘要");

  await user.click(screen.getByRole("button", { name: "生成问题" }));
  expect(videoNoteApi.aiEdit).toHaveBeenLastCalledWith(
    9,
    expect.objectContaining({
      action: "generate_questions",
      instruction: null,
    }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "已重新生成复盘问题",
  );
  expect(screen.getByText("智能兜底")).toBeVisible();
  expect(
    screen.getByText("未使用 AI 模型，结果来自已有资料或规则整理，请核对"),
  ).toBeVisible();
  expect((await findMarkdownEditor()).value).toContain("如何复述学习目标？");
  expect((await findMarkdownEditor()).value).not.toContain("生成复盘问题");

  await user.click(screen.getByRole("button", { name: "生成时间戳" }));
  expect(videoNoteApi.aiEdit).toHaveBeenLastCalledWith(
    9,
    expect.objectContaining({
      action: "generate_timestamps",
      instruction: null,
    }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "已重新生成时间戳提纲",
  );
  expect(screen.getByText("官方章节")).toBeVisible();
  expect(screen.getByText("根据 B 站官方章节整理")).toBeVisible();
  expect((await findMarkdownEditor()).value).toContain("[0:24] 开场目标");

  await user.click(screen.getByRole("button", { name: "撤销 AI 编辑" }));
  expect((await findMarkdownEditor()).value).not.toContain("[0:24] 开场目标");
});

it("discards in-flight AI results and undo history when switching videos", async () => {
  const user = userEvent.setup();
  const otherNote = {
    ...baseNote,
    id: 10,
    bvid: "BVOTHER456",
    title: "另一个视频",
    blocks: [
      { id: "h1", type: "heading", level: 1, text: "另一个视频" },
      { id: "p1", type: "paragraph", text: "B 视频原文" },
    ],
    tags: [],
  };
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: "BVNOTE123",
        title: "AI 视频学习法",
        has_note: true,
        note_id: 9,
        summary_status: "seeded",
        tags: ["AI"],
      },
      {
        bvid: "BVOTHER456",
        title: "另一个视频",
        has_note: true,
        note_id: 10,
        summary_status: "seeded",
        tags: [],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockImplementation(async (_kbId, bvid) => {
    if (bvid === "BVOTHER456") {
      return {
        note: otherNote,
        video: { ...video, bvid: "BVOTHER456", title: "另一个视频" },
        can_create: false,
      };
    }
    return { note: baseNote, video, can_create: false };
  });

  let resolveSummary: (value: {
    message: string;
    tag_suggestions: string[];
    result_source: "ai" | "official" | "fallback";
    operations: unknown[];
  }) => void = () => {};
  vi.mocked(videoNoteApi.generateSummary).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveSummary = resolve;
      }) as never,
  );

  renderWorkspace({ initialBvid: "BVNOTE123" });
  await findMarkdownEditor();

  await user.click(screen.getByRole("button", { name: "生成摘要" }));

  // 生成期间切换到另一个视频
  await user.click(screen.getByRole("button", { name: "选择笔记" }));
  await user.click(await screen.findByText("另一个视频"));
  expect((await findMarkdownEditor()).value).toContain("B 视频原文");

  // 迟到的响应不应写入切换后的笔记，也不应留下可撤销的历史
  resolveSummary({
    message: "已应用摘要",
    tag_suggestions: ["过期标签"],
    result_source: "ai",
    operations: [
      {
        kind: "replace_or_insert_block",
        target_block_id: "p1",
        block: { id: "p1", type: "ai_summary", text: "过期的 AI 摘要" },
      },
    ],
  });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "生成摘要" })).toBeEnabled(),
  );

  expect((await findMarkdownEditor()).value).not.toContain("过期的 AI 摘要");
  expect(screen.getByRole("button", { name: "撤销 AI 编辑" })).toBeDisabled();
});

it("asks before overwriting non-empty summary content and only runs after confirmation", async () => {
  const user = userEvent.setup();
  const noteWithSummary = {
    ...baseNote,
    blocks: [
      ...baseNote.blocks,
      { id: "summary", type: "ai_summary", text: "已有摘要" },
      {
        id: "points",
        type: "key_points",
        items: [{ text: "已有观点" }],
      },
    ],
  };
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: "BVNOTE123",
        title: "AI 视频学习法",
        has_note: true,
        note_id: 9,
        summary_status: "seeded",
        tags: ["AI"],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: noteWithSummary,
    video,
    can_create: false,
  });
  vi.mocked(videoNoteApi.generateSummary).mockResolvedValue({
    message: "摘要已覆盖",
    tag_suggestions: [],
    result_source: "ai",
    operations: [
      {
        kind: "replace_or_insert_block",
        target_block_id: "summary",
        block: { id: "summary", type: "ai_summary", text: "新摘要" },
      },
    ],
  });

  renderWorkspace({ initialBvid: "BVNOTE123" });
  await findMarkdownEditor();

  await user.click(screen.getByRole("button", { name: "生成摘要" }));
  const dialog = screen.getByRole("dialog", { name: "覆盖现有内容？" });
  expect(dialog).toHaveTextContent("摘要");
  expect(dialog).toHaveTextContent("关键观点");
  expect(videoNoteApi.generateSummary).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "取消" }));
  expect(screen.queryByRole("dialog", { name: "覆盖现有内容？" })).toBeNull();
  expect(videoNoteApi.generateSummary).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "生成摘要" }));
  await user.click(screen.getByRole("button", { name: "继续生成并覆盖" }));

  expect(videoNoteApi.generateSummary).toHaveBeenCalledWith(9);
  expect((await findMarkdownEditor()).value).toContain("新摘要");
});

it("runs immediately when the target section is empty", async () => {
  const user = userEvent.setup();
  const noteWithEmptyQuestions = {
    ...baseNote,
    blocks: [
      ...baseNote.blocks,
      {
        id: "questions",
        type: "questions",
        items: [{ text: "  " }, { content: "\n" }],
      },
    ],
  };
  vi.mocked(videoNoteApi.list).mockResolvedValue({
    knowledge_base_id: 7,
    items: [
      {
        bvid: "BVNOTE123",
        title: "AI 视频学习法",
        has_note: true,
        note_id: 9,
        summary_status: "seeded",
        tags: ["AI"],
      },
    ],
  });
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: noteWithEmptyQuestions,
    video,
    can_create: false,
  });
  vi.mocked(videoNoteApi.aiEdit).mockResolvedValue({
    message: "问题已生成",
    tag_suggestions: [],
    result_source: "fallback",
    operations: [],
  });

  renderWorkspace({ initialBvid: "BVNOTE123" });
  await findMarkdownEditor();
  await user.click(screen.getByRole("button", { name: "生成问题" }));

  expect(screen.queryByRole("dialog", { name: "覆盖现有内容？" })).toBeNull();
  expect(videoNoteApi.aiEdit).toHaveBeenCalledWith(
    9,
    expect.objectContaining({ action: "generate_questions" }),
  );
});
