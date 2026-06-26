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
