import { fireEvent, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import {
  baseNote,
  findMarkdownEditor,
  renderWorkspace,
  video,
  videoNoteApi,
} from "./VideoNoteWorkspace.test-utils";

it("autosaves copied Markdown from the toolbar menu and toggles fullscreen", async () => {
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

  const { container } = renderWorkspace({
    initialBvid: "BVNOTE123",
    autosaveDelayMs: 10,
  });

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
  ).toEqual(["笔记名称", "添加待办", "折叠 AI 工具", "导出 Markdown"]);

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
  expect(await screen.findByText("✓ 已复制到剪贴板")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "全屏" }));
  expect(container.querySelector(".video-note-drawer")).toHaveClass(
    "fullscreen",
  );
  expect(container.querySelector(".video-note-workspace")).toHaveClass(
    "fullscreen",
  );
});

it("edits the note title from the toolbar popover", async () => {
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
    title: "新的笔记名称",
  });

  const { container } = renderWorkspace({
    initialBvid: "BVNOTE123",
    autosaveDelayMs: 10,
  });

  await findMarkdownEditor();
  const toolRail = container.querySelector(".video-note-tool-rail");
  await user.click(
    within(toolRail as HTMLElement).getByRole("button", {
      name: "笔记名称",
    }),
  );

  const dialog = await screen.findByRole("dialog", {
    name: "修改笔记名称",
  });
  const titleInput = within(dialog).getByLabelText("笔记名称");
  expect(titleInput).toHaveValue("AI 视频学习法");

  await user.clear(titleInput);
  await user.type(titleInput, "新的笔记名称");
  await user.click(within(dialog).getByRole("button", { name: "保存" }));

  expect(screen.queryByRole("dialog", { name: "修改笔记名称" })).toBeNull();
  await waitFor(() =>
    expect(videoNoteApi.save).toHaveBeenLastCalledWith(
      9,
      expect.objectContaining({
        title: "新的笔记名称",
      }),
    ),
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

  const { container } = renderWorkspace({
    initialBvid: "BVNOTE123",
    autosaveDelayMs: 10,
  });

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
  expect(screen.queryByRole("menu", { name: "Markdown 导出操作" })).toBeNull();
});
