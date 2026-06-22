import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportModal from "@/components/ImportModal";
import { importApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    importApi: {
      ...actual.importApi,
      methods: vi.fn(),
      importUrl: vi.fn(),
      importLocalVideo: vi.fn(),
    },
    sourceBindingApi: {
      ...actual.sourceBindingApi,
      getBilibiliQRCode: vi.fn(),
      pollBilibiliQRCode: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ImportModal", () => {
  it("uploads a selected local video from the video import option", async () => {
    const user = userEvent.setup();
    vi.mocked(importApi.methods).mockResolvedValue({
      methods: [
        {
          id: "video_import",
          label: "导入视频",
          description: "支持视频 URL 或本地视频文件",
          status: "available",
          level: 1,
        },
      ],
    });
    vi.mocked(importApi.importLocalVideo).mockResolvedValue({
      ok: true,
      status: "pending",
      source_type: "local_video",
      message: "已创建本地视频导入任务",
      task_id: "task-local",
      bvid: "LV123",
    });

    render(
      <ImportModal
        open
        knowledgeBaseId={7}
        hasBilibiliBinding={false}
        onClose={vi.fn()}
        onBound={vi.fn()}
        onImported={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /导入视频/ }));
    await user.click(screen.getByRole("button", { name: "本地视频" }));
    await user.upload(
      screen.getByLabelText("选择本地视频文件"),
      new File(["video bytes"], "demo.mp4", { type: "video/mp4" }),
    );
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    await waitFor(() => {
      expect(importApi.importLocalVideo).toHaveBeenCalledWith({
        file: expect.objectContaining({ name: "demo.mp4" }),
        knowledge_base_id: 7,
        title: "demo.mp4",
      });
    });
    expect(screen.getByText("已创建本地视频导入任务")).toBeInTheDocument();
  });

  it("keeps URL import available inside the video import option", async () => {
    const user = userEvent.setup();
    vi.mocked(importApi.methods).mockResolvedValue({
      methods: [
        {
          id: "video_import",
          label: "导入视频",
          description: "支持视频 URL 或本地视频文件",
          status: "available",
          level: 1,
        },
      ],
    });
    vi.mocked(importApi.importUrl).mockResolvedValue({
      ok: true,
      status: "pending",
      source_type: "bilibili_video",
      message: "已创建视频导入任务",
      task_id: "task-url",
      bvid: "BV1xx411c7mD",
    });

    render(
      <ImportModal
        open
        knowledgeBaseId={7}
        hasBilibiliBinding={false}
        onClose={vi.fn()}
        onBound={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /导入视频/ }));
    await user.type(
      screen.getByLabelText("粘贴视频链接"),
      "https://www.bilibili.com/video/BV1xx411c7mD",
    );
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    await waitFor(() => {
      expect(importApi.importUrl).toHaveBeenCalledWith({
        url: "https://www.bilibili.com/video/BV1xx411c7mD",
        source_type: "auto",
        knowledge_base_id: 7,
      });
    });
  });
});
