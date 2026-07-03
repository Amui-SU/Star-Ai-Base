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

    constructor(id: string, options: MockVditorOptions) {
      this.options = options;
      this.element = document.createElement("textarea");
      this.element.setAttribute("aria-label", "Vditor mock editor");
      this.element.value = options.value ?? "";
      this.element.addEventListener("input", () => {
        options.input?.(this.element.value);
      });
      document.getElementById(id)?.append(this.element);
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
    expect(container.querySelector(".video-note-workspace")).toHaveClass(
      "chooser-collapsed",
    );
    expect(container.querySelector(".video-note-list-panel")).toHaveAttribute(
      "hidden",
    );
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

    expect(await findMarkdownEditor()).toBeVisible();
    await user.click(screen.getByRole("button", { name: "选择笔记" }));

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

    await user.click(
      within(toolRail as HTMLElement).getByRole("button", {
        name: /Markdown/,
      }),
    );
    expect(await screen.findByText("AI 视频学习法.md")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "全屏" }));
    expect(container.querySelector(".video-note-drawer")).toHaveClass(
      "fullscreen",
    );
    expect(container.querySelector(".video-note-workspace")).toHaveClass(
      "fullscreen",
    );
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
    expect(sidePanel).not.toHaveClass("collapsed");
    expect(screen.getByRole("button", { name: "折叠 AI 工具" })).toBeVisible();
    expect(
      within(
        container.querySelector(".video-note-tool-rail") as HTMLElement,
      ).getByRole("button", { name: /Markdown/ }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "折叠 AI 工具" }));
    expect(sidePanel).toHaveClass("collapsed");
    expect(screen.queryByRole("button", { name: "生成摘要" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "展开 AI 工具" }));
    expect(sidePanel).not.toHaveClass("collapsed");
    expect(screen.getByRole("button", { name: "生成摘要" })).toBeVisible();
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
    expect((await findMarkdownEditor()).value).toContain("AI 新摘要");

    await user.click(screen.getByRole("button", { name: "撤销 AI 编辑" }));
    expect((await findMarkdownEditor()).value).toContain("旧内容");
  });
});
