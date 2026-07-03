import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
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

interface MockVditorOptions {
  i18n?: Record<string, string>;
  input?: (value: string) => void;
  mode?: string;
  value?: string;
}

const vditorState = vi.hoisted(() => ({
  instances: [] as Array<{
    destroyed: boolean;
    element: HTMLTextAreaElement;
    getValue: () => string;
    options: MockVditorOptions;
    setValue: (value: string) => void;
  }>,
}));

vi.mock("vditor", () => ({
  default: class MockVditor {
    destroyed = false;
    element: HTMLTextAreaElement;
    options: MockVditorOptions;

    constructor(target: string | HTMLElement, options: MockVditorOptions) {
      this.options = options;
      this.element = document.createElement("textarea");
      this.element.setAttribute("aria-label", "Vditor mock editor");
      this.element.value = options.value ?? "";
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      const host =
        typeof target === "string" ? document.getElementById(target) : target;
      host?.append(this.element);
      vditorState.instances.push(this);
    }

    getValue() {
      return this.element.value;
    }

    setValue(value: string) {
      this.element.value = value;
    }

    destroy() {
      this.destroyed = true;
      this.element.remove();
    }
  },
}));

vi.mock("vditor/dist/js/i18n/zh_CN.js", () => {
  window.VditorI18n = { headings: "标题" };
  return {};
});

async function findMarkdownEditor() {
  return (await screen.findByLabelText(
    "Vditor mock editor",
  )) as HTMLTextAreaElement;
}

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
  vditorState.instances.length = 0;
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

    const { container } = render(
      <VideoNoteWorkspace knowledgeBaseId={7} autosaveDelayMs={2000} />,
    );

    expect((await findMarkdownEditor()).value).toContain("旧内容");
    expect(vditorState.instances.at(-1)?.options.i18n).toMatchObject({
      headings: "标题",
    });
    expect(container.querySelector(".video-note-workspace")).toHaveClass(
      "chooser-collapsed",
    );
    expect(container.querySelector(".video-note-chooser-menu")).toBeNull();
    expect(videoNoteApi.detail).toHaveBeenCalledWith(7, "BVNOTE123");
  });

  it("opens selectable videos in a chooser menu and filters by note creation status", async () => {
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

    const { container } = render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={2000}
      />,
    );

    expect(await findMarkdownEditor()).toBeVisible();
    await user.click(screen.getByRole("button", { name: "选择笔记" }));

    const chooserMenu = container.querySelector(".video-note-chooser-menu");
    expect(chooserMenu).not.toBeNull();
    expect(
      within(chooserMenu as HTMLElement).getByRole("button", {
        name: "关闭选择笔记",
      }),
    ).toBeVisible();

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
    expect((await findMarkdownEditor()).value).toContain("旧内容");
  });

  it("edits blocks, autosaves, copies exported Markdown from a toolbar menu, and toggles fullscreen", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
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

    const editor = await findMarkdownEditor();
    fireEvent.input(editor, {
      target: { value: "# AI 视频学习法\n\n新内容" },
    });

    await waitFor(() => expect(videoNoteApi.save).toHaveBeenCalled());
    expect(videoNoteApi.save).toHaveBeenLastCalledWith(
      9,
      expect.objectContaining({
        blocks: expect.arrayContaining([
          expect.objectContaining({
            id: "p1",
            text: "新内容",
            type: "paragraph",
          }),
        ]),
      }),
    );

    const toolRail = container.querySelector(".video-note-tool-rail");
    expect(toolRail).not.toBeNull();
    expect(container.querySelector(".video-note-export-panel")).toBeNull();
    expect(container.querySelector(".video-note-tool-spacer")).toBeNull();

    const toolButtons = within(toolRail as HTMLElement).getAllByRole("button");
    expect(
      toolButtons.map((button) => button.getAttribute("aria-label")),
    ).toEqual(["添加段落", "添加待办", "折叠 AI 工具", "导出 Markdown"]);

    await user.click(
      within(toolRail as HTMLElement).getByRole("button", {
        name: "导出 Markdown",
      }),
    );
    const exportMenu = await screen.findByRole("menu", {
      name: "Markdown 导出操作",
    });
    expect(
      within(exportMenu).getByRole("button", { name: "复制 Markdown" }),
    ).toBeVisible();
    expect(
      within(exportMenu).getByRole("button", { name: "下载 Markdown 文件" }),
    ).toBeVisible();
    expect(screen.queryByLabelText("Markdown 预览")).toBeNull();

    await user.click(
      within(exportMenu).getByRole("button", { name: "复制 Markdown" }),
    );
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("# AI 视频学习法\n"),
    );
    expect(await screen.findByText("已复制 Markdown")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "全屏" }));
    expect(container.querySelector(".video-note-drawer")).toHaveClass(
      "fullscreen",
    );
    expect(container.querySelector(".video-note-workspace")).toHaveClass(
      "fullscreen",
    );
  });

  it("downloads exported Markdown from the toolbar export menu", async () => {
    const user = userEvent.setup();
    const createObjectUrl = vi.fn().mockReturnValue("blob:video-note-md");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
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
      export_filename_template: "学习复盘 - {{bvid}}.md",
    });
    vi.mocked(videoNoteApi.exportMarkdown).mockResolvedValue({
      filename: "学习复盘 - BVNOTE123.md",
      markdown: "# AI 视频学习法\n",
    });

    const { container } = render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={10}
      />,
    );

    await findMarkdownEditor();
    const toolRail = container.querySelector(".video-note-tool-rail");
    await user.click(
      within(toolRail as HTMLElement).getByRole("button", {
        name: "导出 Markdown",
      }),
    );
    const filenameInput = await screen.findByLabelText("导出文件名");
    expect(filenameInput).toHaveAttribute("placeholder", "{{title}}.md");
    fireEvent.change(filenameInput, {
      target: { value: "学习复盘 - {{bvid}}.md" },
    });
    await waitFor(() =>
      expect(videoNoteApi.save).toHaveBeenLastCalledWith(
        9,
        expect.objectContaining({
          export_filename_template: "学习复盘 - {{bvid}}.md",
        }),
      ),
    );

    await user.click(
      await screen.findByRole("button", { name: "下载 Markdown 文件" }),
    );

    await waitFor(() => expect(createObjectUrl).toHaveBeenCalledOnce());
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:video-note-md");
    expect(videoNoteApi.exportMarkdown).toHaveBeenCalledWith(9);
    expect(screen.queryByText("已下载 Markdown")).toBeNull();
    expect(
      screen.queryByRole("menu", { name: "Markdown 导出操作" }),
    ).toBeNull();
  });

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

    const { container } = render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={2000}
      />,
    );

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

    render(
      <VideoNoteWorkspace
        knowledgeBaseId={7}
        initialBvid="BVNOTE123"
        autosaveDelayMs={2000}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "生成摘要" }));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("已应用摘要");
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
    expect((await findMarkdownEditor()).value).toContain("[0:24] 开场目标");

    await user.click(screen.getByRole("button", { name: "撤销 AI 编辑" }));
    expect((await findMarkdownEditor()).value).not.toContain("[0:24] 开场目标");
  });
});
