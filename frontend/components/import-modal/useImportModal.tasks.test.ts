import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { importApi, type ImportTaskStatus } from "@/lib/api";
import { useImportModal } from "./useImportModal";

vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
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
  };
});

const statuses: Record<string, string> = {};
beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(importApi.methods).mockResolvedValue({ methods: [] });
  vi.mocked(importApi.taskStatus).mockImplementation(async (id) => ({
    task_id: id,
    status: statuses[id] ?? "running",
    progress: statuses[id] === "completed" ? 100 : 20,
    current_step: "转写中",
    message: statuses[id] === "interrupted" ? "服务重启，请重新导入" : "",
  }));
  vi.mocked(importApi.importUrl).mockImplementation(async ({ url }) => ({
    ok: true,
    status: "pending",
    source_type: "bilibili_video",
    message: "已创建任务",
    task_id: url,
    bvid: "BVexample",
  }));
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.useRealTimers();
  for (const id of Object.keys(statuses)) delete statuses[id];
});

function mount() {
  const onImported = vi.fn();
  const hook = renderHook(
    ({ open }) =>
      useImportModal({
        open,
        knowledgeBaseId: 7,
        hasBilibiliBinding: false,
        onBound: vi.fn(),
        onClose: vi.fn(),
        onImported,
      }),
    { initialProps: { open: true } },
  );
  return { ...hook, onImported };
}

async function queueUrl(hook: ReturnType<typeof mount>, id: string) {
  act(() => hook.result.current.setUrl(id));
  await act(async () => {
    await hook.result.current.submitUrl();
  });
}

async function tick() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
}

describe("import completion tracking", () => {
  it("notifies once after completion, including a later independent import", async () => {
    const hook = mount();
    await queueUrl(hook, "https://example.com/first");
    expect(hook.onImported).not.toHaveBeenCalled();
    statuses["https://example.com/first"] = "completed";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
    await queueUrl(hook, "https://example.com/second");
    expect(hook.onImported).toHaveBeenCalledTimes(1);
    statuses["https://example.com/second"] = "completed";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(2);
  });

  it.each(["failed", "interrupted"])(
    "stops polling %s tasks without notifying success",
    async (status) => {
      const hook = mount();
      await queueUrl(hook, "https://example.com/terminal");
      statuses["https://example.com/terminal"] = status;
      await tick();
      expect(hook.result.current.taskProgress[0].status).toBe(status);
      const polls = vi.mocked(importApi.taskStatus).mock.calls.length;
      await tick();
      expect(importApi.taskStatus).toHaveBeenCalledTimes(polls);
      expect(hook.onImported).not.toHaveBeenCalled();
    },
  );

  it("continues tracking and refreshes when the dialog has been closed", async () => {
    const hook = mount();
    await queueUrl(hook, "https://example.com/closed");
    hook.rerender({ open: false });
    statuses["https://example.com/closed"] = "completed";
    await tick();
    expect(hook.result.current.taskProgress[0]?.status).toBe("completed");
    expect(hook.onImported).toHaveBeenCalledTimes(1);
  });

  it("notifies an independent finished batch without waiting for another batch", async () => {
    const hook = mount();
    await queueUrl(hook, "https://example.com/slow");
    await queueUrl(hook, "https://example.com/fast");
    statuses["https://example.com/fast"] = "completed";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
    statuses["https://example.com/slow"] = "completed";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(2);
  });

  it("waits for all selected parts and emits one refresh for partial success", async () => {
    vi.mocked(importApi.detectMultiPart).mockResolvedValue({
      ok: true,
      message: "分P",
      multi_part_info: {
        bvid: "BV1xx411c7mD",
        title: "教程",
        is_multi_part: true,
        total_parts: 2,
        pages: [
          { cid: 1, page: 1, part: "一", duration: 60 },
          { cid: 2, page: 2, part: "二", duration: 60 },
        ],
      },
    });
    vi.mocked(importApi.importMultiPart).mockResolvedValue({
      ok: true,
      message: "已创建",
      bvid: "BV1xx411c7mD",
      total_selected: 2,
      task_ids: ["part-1", "part-2"],
      import_summary: "两P",
    });
    const hook = mount();
    await queueUrl(hook, "https://www.bilibili.com/video/BV1xx411c7mD");
    await act(async () => {
      await hook.result.current.submitMultiPart();
    });
    statuses["part-1"] = "completed";
    await tick();
    expect(hook.onImported).not.toHaveBeenCalled();
    statuses["part-2"] = "interrupted";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
  });

  it("waits for local video completion before notifying", async () => {
    vi.mocked(importApi.importLocalVideo).mockResolvedValue({
      ok: true,
      status: "pending",
      source_type: "local_video",
      message: "已创建",
      task_id: "local",
      bvid: "LVtest",
    });
    const hook = mount();
    act(() =>
      hook.result.current.setLocalVideoFile(new File(["bytes"], "demo.mp4")),
    );
    await act(async () => {
      await hook.result.current.submitLocalVideo();
    });
    expect(hook.onImported).not.toHaveBeenCalled();
    statuses.local = "completed";
    await tick();
    expect(hook.onImported).toHaveBeenCalledTimes(1);
  });

  it("refreshes a completed batch while another batch's status request never resolves", async () => {
    vi.mocked(importApi.taskStatus).mockImplementation((id) =>
      id === "https://example.com/stalled"
        ? new Promise(() => {})
        : Promise.resolve({
            task_id: id,
            status: "completed",
            progress: 100,
            message: "",
          }),
    );
    const hook = mount();
    await queueUrl(hook, "https://example.com/stalled");
    await queueUrl(hook, "https://example.com/completed");
    expect(
      hook.result.current.taskProgress.find((task) =>
        task.id.endsWith("completed"),
      )?.status,
    ).toBe("completed");
    expect(hook.onImported).toHaveBeenCalledTimes(1);
  });

  it("does not overlap polling while a status response is pending", async () => {
    let resolve!: (value: ImportTaskStatus) => void;
    vi.mocked(importApi.taskStatus).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const hook = mount();
    await queueUrl(hook, "https://example.com/slow-response");
    await tick();
    expect(importApi.taskStatus).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve({
        task_id: "https://example.com/slow-response",
        status: "completed",
        progress: 100,
        current_step: "完成",
        message: "",
      });
    });
    expect(hook.onImported).toHaveBeenCalledTimes(1);
  });
});
