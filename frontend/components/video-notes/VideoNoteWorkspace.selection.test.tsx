import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import {
  baseNote,
  findMarkdownEditor,
  renderWorkspace,
  video,
  videoNoteApi,
  vditorState,
} from "./VideoNoteWorkspace.test-utils";

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

  const { container } = renderWorkspace();

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

  const { container } = renderWorkspace({ initialBvid: "BVNOTE123" });

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

  renderWorkspace({ initialBvid: "BVNOTE123", autosaveDelayMs: 20 });

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

it("shows a workspace error when the note list cannot reach the backend", async () => {
  const consoleError = vi
    .spyOn(console, "error")
    .mockImplementation(() => undefined);
  vi.mocked(videoNoteApi.list).mockRejectedValue(
    new Error(
      "无法连接到后端服务（http://localhost:8000）。请确认后端已启动，且接口地址可访问。",
    ),
  );

  try {
    renderWorkspace();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "无法加载视频笔记列表：无法连接到后端服务（http://localhost:8000）。请确认后端已启动，且接口地址可访问。",
    );
    expect(videoNoteApi.detail).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  } finally {
    consoleError.mockRestore();
  }
});

it("shows a workspace error when the selected note detail fails to load", async () => {
  const consoleError = vi
    .spyOn(console, "error")
    .mockImplementation(() => undefined);
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
    ],
  });
  vi.mocked(videoNoteApi.detail).mockRejectedValue(new Error("后端暂时不可用"));

  try {
    renderWorkspace({ initialBvid: "BVNOTE123" });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "无法加载视频信息：后端暂时不可用",
    );
    expect(consoleError).not.toHaveBeenCalled();
  } finally {
    consoleError.mockRestore();
  }
});
