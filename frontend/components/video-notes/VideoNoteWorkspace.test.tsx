import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import VideoNoteWorkspace from "./VideoNoteWorkspace";
import { videoNoteApi, type VideoNote } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    videoNoteApi: {
      list: vi.fn(),
      detail: vi.fn(),
      create: vi.fn(),
      save: vi.fn(),
      exportMarkdown: vi.fn(),
      generateSummary: vi.fn(),
      aiEdit: vi.fn(),
    },
  };
});

const baseNote: VideoNote = {
  id: 9,
  user_id: 1,
  workspace_id: 1,
  knowledge_base_id: 7,
  bvid: "BVNOTE123",
  title: "AI 视频学习法",
  template_id: "standard",
  blocks: [
    { id: "h1", type: "heading", level: 1, text: "AI 视频学习法" },
    { id: "p1", type: "paragraph", text: "旧内容" },
  ],
  tags: ["AI"],
  summary_status: "seeded",
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  video: null,
};

const video = {
  bvid: "BVNOTE123",
  title: "AI 视频学习法",
  folder_title: "学习收藏夹",
  owner_name: "知识区 UP",
  url: "https://www.bilibili.com/video/BVNOTE123",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("VideoNoteWorkspace", () => {
  it("opens directly into the first existing note when no video is preselected", async () => {
    vi.mocked(videoNoteApi.list).mockResolvedValue({
      knowledge_base_id: 7,
      items: [
        {
          bvid: "BVEMPTY",
          title: "还没有笔记的视频",
          folder_title: "学习收藏夹",
          has_note: false,
          summary_status: "not_created",
          tags: [],
        },
        {
          bvid: "BVNOTE123",
          title: "AI 视频学习法",
          folder_title: "学习收藏夹",
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

    render(<VideoNoteWorkspace knowledgeBaseId={7} autosaveDelayMs={2000} />);

    expect(await screen.findByDisplayValue("旧内容")).toBeVisible();
    expect(videoNoteApi.detail).toHaveBeenCalledWith(7, "BVNOTE123");
  });

  it("filters selectable videos by note creation status", async () => {
    const user = userEvent.setup();
    vi.mocked(videoNoteApi.list).mockResolvedValue({
      knowledge_base_id: 7,
      items: [
        {
          bvid: "BVNOTE123",
          title: "AI 视频学习法",
          folder_title: "学习收藏夹",
          has_note: true,
          note_id: 9,
          summary_status: "seeded",
          tags: ["AI"],
        },
        {
          bvid: "BVEMPTY",
          title: "还没有笔记的视频",
          folder_title: "学习收藏夹",
          has_note: false,
          summary_status: "not_created",
          tags: [],
        },
      ],
    });
    vi.mocked(videoNoteApi.detail).mockResolvedValue({
      note: baseNote,
      video,
      can_create: false,
    });

    render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={2000}
      />,
    );

    expect(await screen.findByText("AI 视频学习法")).toBeVisible();
    expect(screen.getByText("还没有笔记的视频")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "未创建 1" }));
    expect(screen.queryByText("AI 视频学习法")).toBeNull();
    expect(screen.getByText("还没有笔记的视频")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "已有笔记 1" }));
    expect(screen.getByText("AI 视频学习法")).toBeVisible();
    expect(screen.queryByText("还没有笔记的视频")).toBeNull();
  });

  it("loads the list and creates a standard template note", async () => {
    const user = userEvent.setup();
    vi.mocked(videoNoteApi.list).mockResolvedValue({
      knowledge_base_id: 7,
      items: [
        {
          bvid: "BVNOTE123",
          title: "AI 视频学习法",
          folder_title: "学习收藏夹",
          has_note: false,
          summary_status: "not_created",
          tags: [],
        },
      ],
    });
    vi.mocked(videoNoteApi.detail).mockResolvedValue({
      note: null,
      video,
      can_create: true,
    });
    vi.mocked(videoNoteApi.create).mockResolvedValue(baseNote);

    render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={20}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /标准模板/ }));

    await waitFor(() =>
      expect(videoNoteApi.create).toHaveBeenCalledWith({
        knowledge_base_id: 7,
        bvid: "BVNOTE123",
        template_id: "standard",
      }),
    );
    expect(await screen.findByDisplayValue("旧内容")).toBeVisible();
  });

  it("edits blocks, autosaves, exports Markdown, and toggles fullscreen", async () => {
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
    vi.mocked(videoNoteApi.save).mockResolvedValue({
      ...baseNote,
      blocks: [{ id: "p1", type: "paragraph", text: "新内容" }],
    });
    vi.mocked(videoNoteApi.exportMarkdown).mockResolvedValue({
      filename: "AI 视频学习法.md",
      markdown: "# AI 视频学习法\n",
    });

    const { container } = render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={10}
      />,
    );

    const paragraph = await screen.findByDisplayValue("旧内容");
    await user.clear(paragraph);
    await user.type(paragraph, "新内容");

    await waitFor(() => expect(videoNoteApi.save).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: "导出 Markdown" }));
    expect(await screen.findByText("AI 视频学习法.md")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "全屏" }));
    expect(container.querySelector(".video-note-workspace")).toHaveClass(
      "fullscreen",
    );
  });

  it("applies AI summary suggestions and can undo them", async () => {
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
      message: "ok",
      tag_suggestions: ["学习"],
      operations: [
        {
          kind: "replace_or_insert_block",
          target_block_id: "p1",
          block: { id: "p1", type: "ai_summary", text: "AI 新摘要" },
        },
      ],
    });

    render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={2000}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "生成摘要" }));
    expect(await screen.findByDisplayValue("AI 新摘要")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "撤销 AI 编辑" }));
    expect(screen.getByDisplayValue("旧内容")).toBeVisible();
  });
});
