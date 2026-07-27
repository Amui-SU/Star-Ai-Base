import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportModal from "@/components/ImportModal";
import { importApi, sourceBindingApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    importApi: {
      ...actual.importApi,
      methods: vi.fn(),
      importUrl: vi.fn(),
      importLocalVideo: vi.fn(),
      detectMultiPart: vi.fn(),
      importMultiPart: vi.fn(),
      taskStatus: vi.fn(),
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
  vi.useRealTimers();
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
    vi.mocked(importApi.detectMultiPart).mockResolvedValue({
      ok: true,
      message: "单P视频",
      multi_part_info: {
        bvid: "BV1xx411c7mD",
        title: "单P视频",
        is_multi_part: false,
        total_parts: 1,
        pages: [{ cid: 111, page: 1, part: "", duration: 300 }],
      },
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

  it("shows part selection for multi-part videos and imports the chosen parts", async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
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
    vi.mocked(importApi.detectMultiPart).mockResolvedValue({
      ok: true,
      message: "检测到分P视频，共 3 个分P",
      multi_part_info: {
        bvid: "BV1xx411c7mD",
        title: "教程合集",
        is_multi_part: true,
        total_parts: 3,
        pages: [
          { cid: 111, page: 1, part: "第一讲", duration: 400 },
          { cid: 222, page: 2, part: "第二讲", duration: 500 },
          { cid: 333, page: 3, part: "第三讲", duration: 600 },
        ],
      },
    });
    vi.mocked(importApi.importMultiPart).mockResolvedValue({
      ok: true,
      message: "已创建 2 个导入任务",
      bvid: "BV1xx411c7mD",
      total_selected: 2,
      task_ids: ["task-1", "task-2"],
      import_summary: "将导入《教程合集》的 2 个分P（P1, P3）",
    });
    vi.mocked(importApi.taskStatus).mockImplementation(async (taskId) => ({
      task_id: taskId,
      status: taskId === "task-1" ? "completed" : "running",
      progress: taskId === "task-1" ? 100 : 36,
      current_step: taskId === "task-1" ? "导入完成" : "提取视频内容...",
      message: "",
    }));

    render(
      <ImportModal
        open
        knowledgeBaseId={7}
        hasBilibiliBinding={false}
        onClose={vi.fn()}
        onBound={vi.fn()}
        onImported={onImported}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /导入视频/ }));
    await user.type(
      screen.getByLabelText("粘贴视频链接"),
      "https://www.bilibili.com/video/BV1xx411c7mD",
    );
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    // 检测到分P后展示选择列表，默认全选
    expect(await screen.findByText("教程合集")).toBeInTheDocument();
    expect(screen.getByText(/共 3 个分P，已选 3 个/)).toBeInTheDocument();
    expect(importApi.importUrl).not.toHaveBeenCalled();

    // 取消勾选 P2
    await user.click(screen.getByRole("checkbox", { name: /P2: 第二讲/ }));
    expect(screen.getByText(/已选 2 个/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "导入所选分P (2)" }));

    await waitFor(() => {
      expect(importApi.importMultiPart).toHaveBeenCalledWith({
        url: "https://www.bilibili.com/video/BV1xx411c7mD",
        knowledge_base_id: 7,
        page_indices: [1, 3],
      });
    });
    expect(onImported).toHaveBeenCalled();
    expect(screen.getByText("已创建 2 个导入任务")).toBeInTheDocument();

    // 导入后轮询任务状态并展示每个分P的进度
    const progressList = await screen.findByRole("list", {
      name: "导入任务进度",
    });
    await waitFor(() => {
      expect(progressList).toHaveTextContent("P1");
      expect(progressList).toHaveTextContent("✓ 完成");
      expect(progressList).toHaveTextContent("P3");
      expect(progressList).toHaveTextContent("提取视频内容... 36%");
    });
  });

  it("stops Bilibili QR polling after the maximum wait time", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.mocked(importApi.methods).mockResolvedValue({
      methods: [
        {
          id: "bilibili_favorites",
          label: "B 站收藏夹",
          description: "扫码绑定账号后导入收藏夹资料",
          status: "available",
          level: 2,
        },
      ],
    });
    vi.mocked(sourceBindingApi.getBilibiliQRCode).mockResolvedValue({
      qrcode_key: "qr-key",
      qrcode_url: "https://example.com/qr",
      qrcode_image_base64:
        "data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA=",
    });
    vi.mocked(sourceBindingApi.pollBilibiliQRCode).mockResolvedValue({
      status: "waiting",
      message: "等待扫码",
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

    await user.click(await screen.findByRole("button", { name: /B 站收藏夹/ }));
    await screen.findByAltText("B站绑定二维码");

    for (let attempt = 0; attempt < 150; attempt += 1) {
      await vi.advanceTimersByTimeAsync(2000);
    }

    expect(
      await screen.findByText("二维码等待超时，请重新获取"),
    ).toBeInTheDocument();
    expect(sourceBindingApi.pollBilibiliQRCode).toHaveBeenCalledTimes(150);

    await vi.advanceTimersByTimeAsync(2000);

    expect(sourceBindingApi.pollBilibiliQRCode).toHaveBeenCalledTimes(150);
  });
});
