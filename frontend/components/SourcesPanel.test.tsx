import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SourcesPanel from "@/components/SourcesPanel";
import { knowledgeBaseApi, sourceBindingApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    sourceBindingApi: {
      ...actual.sourceBindingApi,
      getFavorites: vi.fn(),
      getAllFavoriteVideos: vi.fn(),
    },
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      stats: vi.fn(),
      build: vi.fn(),
      getBuildStatus: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SourcesPanel", () => {
  it("uses the dedicated empty layout when imported favorites have no content", async () => {
    vi.mocked(sourceBindingApi.getFavorites).mockResolvedValue([]);
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 1,
      workspace_id: 1,
      total_videos: 0,
      folders: [],
      scoped: true,
    });

    const onImportClick = vi.fn();
    const { container } = render(
      <SourcesPanel
        sourceBindingId={1}
        knowledgeBaseId={1}
        onImportClick={onImportClick}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("暂无收藏夹资料")).toBeInTheDocument();
    });

    expect(container.querySelector(".panel-inner")).toHaveClass(
      "sources-panel-empty",
    );
    expect(
      screen.getByRole("button", { name: "导入更多资料" }),
    ).toBeInTheDocument();
  });

  it("can ingest a single selected video without selecting the whole folder", async () => {
    const user = userEvent.setup();
    vi.mocked(sourceBindingApi.getFavorites).mockResolvedValue([
      {
        media_id: 10,
        title: "Folder A",
        media_count: 2,
        is_selected: true,
      },
    ]);
    vi.mocked(sourceBindingApi.getAllFavoriteVideos).mockResolvedValue({
      total: 2,
      valid: 2,
      videos: [
        { bvid: "BV1ONLY", title: "Video one" },
        { bvid: "BV1SKIP", title: "Video two" },
      ],
    });
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 1,
      workspace_id: 1,
      total_videos: 0,
      folders: [],
      scoped: true,
    });
    vi.mocked(knowledgeBaseApi.build).mockResolvedValue({
      task_id: "task-1",
      status: "pending",
      workspace_id: 1,
      knowledge_base_id: 1,
      source_binding_id: 7,
    });
    vi.mocked(knowledgeBaseApi.getBuildStatus).mockResolvedValue({
      task_id: "task-1",
      status: "completed",
      progress: 100,
      current_step: "done",
      total_videos: 1,
      processed_videos: 1,
      message: "done",
    });

    const { container } = render(
      <SourcesPanel sourceBindingId={7} knowledgeBaseId={1} />,
    );

    await user.click(await screen.findByText("Folder A"));
    await user.click(await screen.findByLabelText("选择视频 Video one"));

    const ingestButton = container.querySelector(
      ".sources-ingest-button",
    ) as HTMLButtonElement;
    await user.click(ingestButton);

    await waitFor(() => {
      expect(knowledgeBaseApi.build).toHaveBeenCalledWith(1, {
        source_binding_id: 7,
        folder_ids: [],
        video_folder_ids: [10],
        bvids: ["BV1ONLY"],
      });
    });
  });

  it("uses fallback names for corrupted folder and video titles", async () => {
    const user = userEvent.setup();
    vi.mocked(sourceBindingApi.getFavorites).mockResolvedValue([
      {
        media_id: 10,
        title: "????",
        media_count: 1,
        is_selected: true,
      },
    ]);
    vi.mocked(sourceBindingApi.getAllFavoriteVideos).mockResolvedValue({
      total: 1,
      valid: 1,
      videos: [
        {
          bvid: "BVEMPTY",
          title: "",
          display_title: "",
          original_title: "????",
          custom_title: null,
        },
      ],
    });
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 1,
      workspace_id: 1,
      total_videos: 0,
      folders: [],
      scoped: true,
    });

    render(<SourcesPanel sourceBindingId={7} knowledgeBaseId={1} />);

    await user.click(await screen.findByText("未命名收藏夹"));

    expect(screen.queryByText("????")).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "选择收藏夹 未命名收藏夹" }),
    ).toBeInTheDocument();
    expect(await screen.findAllByText("未命名视频")).not.toHaveLength(0);
    expect(
      screen.getByRole("checkbox", { name: "选择视频 未命名视频" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "未命名视频" }),
    ).toBeInTheDocument();
  });

  it("stops polling and shows a restart hint when a build is interrupted", async () => {
    const user = userEvent.setup();
    vi.mocked(sourceBindingApi.getFavorites).mockResolvedValue([
      {
        media_id: 10,
        title: "Folder A",
        media_count: 1,
        is_selected: true,
      },
    ]);
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 1,
      workspace_id: 1,
      total_videos: 0,
      folders: [],
      scoped: true,
    });
    vi.mocked(knowledgeBaseApi.build).mockResolvedValue({
      task_id: "task-interrupted",
      status: "pending",
      workspace_id: 1,
      knowledge_base_id: 1,
      source_binding_id: 7,
    });
    vi.mocked(knowledgeBaseApi.getBuildStatus).mockResolvedValue({
      task_id: "task-interrupted",
      status: "interrupted",
      progress: 48,
      current_step: "任务已中断，请重新发起",
      total_videos: 1,
      processed_videos: 0,
      message: "服务重启或后台任务中断，任务未自动恢复，请重新发起。",
    });

    const { container } = render(
      <SourcesPanel sourceBindingId={7} knowledgeBaseId={1} />,
    );

    await user.click(await screen.findByLabelText("选择收藏夹 Folder A"));
    const ingestButton = container.querySelector(
      ".sources-ingest-button",
    ) as HTMLButtonElement;
    await user.click(ingestButton);

    await waitFor(() => {
      expect(screen.getByText(/构建已中断/)).toBeInTheDocument();
    });
    expect(screen.getByText(/请重新发起/)).toBeInTheDocument();
  });

  it("opens the Bilibili player modal for a selected video", async () => {
    const user = userEvent.setup();
    vi.mocked(sourceBindingApi.getFavorites).mockResolvedValue([
      {
        media_id: 10,
        title: "Folder A",
        media_count: 1,
        is_selected: true,
      },
    ]);
    vi.mocked(sourceBindingApi.getAllFavoriteVideos).mockResolvedValue({
      total: 1,
      valid: 1,
      videos: [{ bvid: "BV1PLAY", title: "Video one" }],
    });
    vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
      knowledge_base_id: 1,
      workspace_id: 1,
      total_videos: 0,
      folders: [],
      scoped: true,
    });

    render(<SourcesPanel sourceBindingId={7} knowledgeBaseId={1} />);

    await user.click(await screen.findByText("Folder A"));
    await user.click(screen.getByRole("button", { name: "播放 Video one" }));

    const iframe = document.querySelector(".video-player-frame");
    expect(iframe).toHaveAttribute(
      "src",
      expect.stringContaining("bvid=BV1PLAY"),
    );
    expect(screen.getByRole("button", { name: "关闭" })).toHaveAttribute(
      "type",
      "button",
    );
  });
});
