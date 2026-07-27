import {
  act,
  fireEvent,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
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
import VideoNoteWorkspace from "./VideoNoteWorkspace";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function advanceTimersByTime(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
  });
}

const searchResult = (bvid: string, title: string, knowledgeBaseId = 7) => ({
  knowledge_base_id: knowledgeBaseId,
  items: [
    {
      bvid,
      title,
      folder_title: "搜索结果",
      has_note: true,
      note_id: 9,
      summary_status: "seeded" as const,
      tags: [],
    },
  ],
});

it("debounces incremental search input and requests only the final query", async () => {
  vi.useFakeTimers();
  vi.mocked(videoNoteApi.list).mockResolvedValue(
    searchResult("BVINITIAL", "初始结果"),
  );
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  renderWorkspace({ initialBvid: "BVINITIAL" });
  await advanceTimersByTime(0);

  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));
  const searchInput = screen.getByRole("searchbox", {
    name: "搜索视频笔记",
  });
  fireEvent.change(searchInput, { target: { value: "视" } });
  fireEvent.change(searchInput, { target: { value: "视频" } });
  fireEvent.change(searchInput, { target: { value: "视频笔记" } });

  expect(videoNoteApi.list).toHaveBeenCalledTimes(1);
  await advanceTimersByTime(299);
  expect(videoNoteApi.list).toHaveBeenCalledTimes(1);

  await advanceTimersByTime(1);
  await advanceTimersByTime(0);
  expect(videoNoteApi.list).toHaveBeenCalledTimes(2);
  expect(videoNoteApi.list).toHaveBeenLastCalledWith({
    knowledgeBaseId: 7,
    q: "视频笔记",
    includeBodySearch: false,
  });
});

it("ignores an old search response that resolves after the final query", async () => {
  vi.useFakeTimers();
  const oldRequest = deferred<ReturnType<typeof searchResult>>();
  const newRequest = deferred<ReturnType<typeof searchResult>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  renderWorkspace();
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索视频笔记" }), {
    target: { value: "最终" },
  });
  await advanceTimersByTime(300);
  await advanceTimersByTime(0);

  await act(async () => {
    newRequest.resolve(searchResult("BVNEW", "最终结果"));
    await newRequest.promise;
  });
  await advanceTimersByTime(0);
  expect(screen.getByText("最终结果")).toBeVisible();
  expect(videoNoteApi.detail).toHaveBeenCalledWith(7, "BVNEW");

  await act(async () => {
    oldRequest.resolve(searchResult("BVOLD", "过期结果"));
    await oldRequest.promise;
  });
  expect(screen.queryByText("过期结果")).toBeNull();
  expect(screen.getByText("最终结果")).toBeVisible();
  expect(videoNoteApi.detail).not.toHaveBeenCalledWith(7, "BVOLD");
});

it("ignores an old search rejection after the query changes", async () => {
  vi.useFakeTimers();
  const oldRequest = deferred<ReturnType<typeof searchResult>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockResolvedValueOnce(searchResult("BVNEW", "最终结果"));
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  renderWorkspace();
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索视频笔记" }), {
    target: { value: "最终" },
  });

  await act(async () => {
    oldRequest.reject(new Error("过期请求失败"));
    try {
      await oldRequest.promise;
    } catch {
      // The component handles the rejection; this await only flushes it.
    }
  });

  expect(screen.queryByRole("alert")).toBeNull();

  await advanceTimersByTime(300);
  await advanceTimersByTime(0);
  expect(screen.getByText("最终结果")).toBeVisible();
});

it("keeps the final query loading when an old request settles", async () => {
  vi.useFakeTimers();
  const oldRequest = deferred<ReturnType<typeof searchResult>>();
  const newRequest = deferred<ReturnType<typeof searchResult>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);

  renderWorkspace();
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索视频笔记" }), {
    target: { value: "最终" },
  });
  await advanceTimersByTime(300);
  await advanceTimersByTime(0);

  await act(async () => {
    oldRequest.resolve(searchResult("BVOLD", "过期结果"));
    await oldRequest.promise;
  });

  expect(screen.getByText("加载中...")).toBeVisible();
  expect(screen.queryByText("过期结果")).toBeNull();

  await act(async () => {
    newRequest.resolve(searchResult("BVNEW", "最终结果"));
    await newRequest.promise;
  });
  expect(screen.queryByText("加载中...")).toBeNull();
  expect(screen.getByText("最终结果")).toBeVisible();
});

it("requests immediately when body search or the knowledge base changes", async () => {
  vi.useFakeTimers();
  vi.mocked(videoNoteApi.list).mockResolvedValue(
    searchResult("BVINITIAL", "初始结果"),
  );
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  const { rerender } = renderWorkspace({ initialBvid: "BVINITIAL" });
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));

  fireEvent.click(screen.getByRole("checkbox", { name: "搜索正文" }));
  await advanceTimersByTime(0);
  expect(videoNoteApi.list).toHaveBeenCalledTimes(2);
  expect(videoNoteApi.list).toHaveBeenLastCalledWith({
    knowledgeBaseId: 7,
    q: undefined,
    includeBodySearch: true,
  });

  rerender(
    <VideoNoteWorkspace
      knowledgeBaseId={8}
      initialBvid="BVINITIAL"
      autosaveDelayMs={2000}
    />,
  );
  await advanceTimersByTime(0);
  expect(videoNoteApi.list).toHaveBeenCalledTimes(3);
  expect(videoNoteApi.list).toHaveBeenLastCalledWith({
    knowledgeBaseId: 8,
    q: undefined,
    includeBodySearch: true,
  });
});

it("invalidates a pending list response as soon as the knowledge base changes", async () => {
  vi.useFakeTimers();
  const oldRequest = deferred<ReturnType<typeof searchResult>>();
  const newRequest = deferred<ReturnType<typeof searchResult>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);
  vi.mocked(videoNoteApi.detail).mockResolvedValue({
    note: baseNote,
    video,
    can_create: false,
  });

  const { rerender } = renderWorkspace();
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));

  rerender(<VideoNoteWorkspace knowledgeBaseId={8} autosaveDelayMs={2000} />);
  await act(async () => {
    oldRequest.resolve(searchResult("BVOLD", "旧知识库结果"));
    await oldRequest.promise;
  });

  expect(screen.queryByText("旧知识库结果")).toBeNull();
  expect(screen.getByText("加载中...")).toBeVisible();
  expect(videoNoteApi.detail).not.toHaveBeenCalledWith(7, "BVOLD");

  await advanceTimersByTime(0);
  await act(async () => {
    newRequest.resolve(searchResult("BVNEW", "新知识库结果", 8));
    await newRequest.promise;
  });
  await advanceTimersByTime(0);

  expect(screen.getByText("新知识库结果")).toBeVisible();
  expect(screen.queryByText("加载中...")).toBeNull();
  expect(videoNoteApi.detail).toHaveBeenCalledWith(8, "BVNEW");
  expect(videoNoteApi.detail).not.toHaveBeenCalledWith(7, "BVOLD");
});

it("ignores a pending list rejection as soon as the knowledge base changes", async () => {
  vi.useFakeTimers();
  const oldRequest = deferred<ReturnType<typeof searchResult>>();
  const newRequest = deferred<ReturnType<typeof searchResult>>();
  vi.mocked(videoNoteApi.list)
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);

  const { rerender } = renderWorkspace();
  await advanceTimersByTime(0);
  fireEvent.click(screen.getByRole("button", { name: "选择笔记" }));

  rerender(<VideoNoteWorkspace knowledgeBaseId={8} autosaveDelayMs={2000} />);
  await act(async () => {
    oldRequest.reject(new Error("旧知识库请求失败"));
    try {
      await oldRequest.promise;
    } catch {
      // The component handles the rejection; this await only flushes it.
    }
  });

  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("加载中...")).toBeVisible();

  await advanceTimersByTime(0);
  await act(async () => {
    newRequest.resolve(searchResult("BVNEW", "新知识库结果", 8));
    await newRequest.promise;
  });

  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByText("加载中...")).toBeNull();
  expect(screen.getByText("新知识库结果")).toBeVisible();
});

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
