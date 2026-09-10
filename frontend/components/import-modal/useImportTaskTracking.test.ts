import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError, importApi, type ImportTaskStatus } from "@/lib/api";
import { useImportTaskTracking } from "./useImportTaskTracking";

vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
  return { ...actual, importApi: { ...actual.importApi, taskStatus: vi.fn() } };
});
beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.useRealTimers();
});
const running = (id = "a"): ImportTaskStatus => ({
  task_id: id,
  status: "running",
  progress: 20,
  message: "working",
});
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
async function mount() {
  const onImported = vi.fn();
  const hook = renderHook(({ callback }) => useImportTaskTracking(callback), {
    initialProps: { callback: onImported },
  });
  await act(async () =>
    hook.result.current.trackTasks([{ id: "a", label: "A" }]),
  );
  return { ...hook, onImported };
}

it.each([401, 403, 404])(
  "terminates HTTP %s without another request or success notification",
  async (status) => {
    vi.mocked(importApi.taskStatus).mockRejectedValue(
      new ApiError("gone", status),
    );
    const hook = await mount();
    expect(hook.result.current.taskProgress[0].status).toBe("interrupted");
    await advance(60000);
    expect(importApi.taskStatus).toHaveBeenCalledTimes(1);
    expect(hook.onImported).not.toHaveBeenCalled();
  },
);

it("times out an abort-ignoring request and stops after five failures", async () => {
  const signals: AbortSignal[] = [];
  vi.mocked(importApi.taskStatus).mockImplementation((_id, signal) => {
    signals.push(signal!);
    return new Promise(() => {});
  });
  const hook = await mount();
  await advance(9999);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(1);
  await advance(1);
  expect(signals[0]?.aborted).toBe(true);
  await advance(48000);
  expect(hook.result.current.taskProgress[0].status).toBe("interrupted");
  expect(importApi.taskStatus).toHaveBeenCalledTimes(5);
  await advance(60000);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(5);
});

it("resets consecutive failures after recovery and stops on completed", async () => {
  vi.mocked(importApi.taskStatus)
    .mockRejectedValueOnce(new ApiError("retry", 503))
    .mockRejectedValueOnce(new Error("network"))
    .mockRejectedValueOnce(new Error("network"))
    .mockRejectedValueOnce(new Error("network"))
    .mockResolvedValueOnce(running())
    .mockRejectedValueOnce(new Error("network"))
    .mockResolvedValue({ ...running(), status: "completed", progress: 100 });
  const hook = await mount();
  await advance(12000);
  expect(hook.result.current.taskProgress[0].status).toBe("completed");
  expect(hook.onImported).toHaveBeenCalledTimes(1);
  await advance(12000);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(7);
});

it("stops even healthy nonterminal tracking at two hours", async () => {
  vi.mocked(importApi.taskStatus).mockResolvedValue(running());
  const hook = await mount();
  await advance(2 * 60 * 60 * 1000);
  expect(hook.result.current.taskProgress[0].status).toBe("interrupted");
  const count = vi.mocked(importApi.taskStatus).mock.calls.length;
  await advance(60000);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(count);
});

it("preserves in-flight ownership across new batches and callback changes, then aborts on unmount", async () => {
  let finish!: (status: ImportTaskStatus) => void;
  const signals: AbortSignal[] = [];
  vi.mocked(importApi.taskStatus).mockImplementation((id, signal) => {
    signals.push(signal!);
    return id === "a"
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : Promise.resolve({ ...running(id), status: "completed" });
  });
  const hook = await mount();
  const callback = vi.fn();
  hook.rerender({ callback });
  await act(async () =>
    hook.result.current.trackTasks([{ id: "b", label: "B" }]),
  );
  expect(signals[0]?.aborted).toBe(false);
  expect(
    vi.mocked(importApi.taskStatus).mock.calls.filter(([id]) => id === "a"),
  ).toHaveLength(1);
  expect(callback).toHaveBeenCalledTimes(1);
  hook.unmount();
  expect(signals[0]?.aborted).toBe(true);
  await act(async () => finish({ ...running(), status: "completed" }));
  await advance(60000);
  expect(callback).toHaveBeenCalledTimes(1);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(2);
});

it("does not create overlapping requests for duplicate tasks", async () => {
  vi.mocked(importApi.taskStatus).mockReturnValue(new Promise(() => {}));
  const hook = await mount();
  await act(async () =>
    hook.result.current.trackTasks([
      { id: "a", label: "A" },
      { id: "a", label: "A" },
    ]),
  );
  expect(importApi.taskStatus).toHaveBeenCalledTimes(1);
});

it("ignores the late result of a timed-out request after the retry completes", async () => {
  let late!: (status: ImportTaskStatus) => void;
  vi.mocked(importApi.taskStatus)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        late = resolve;
      }),
    )
    .mockResolvedValue({ ...running(), status: "completed", progress: 100 });
  const hook = await mount();
  await advance(12000);
  expect(hook.result.current.taskProgress[0].status).toBe("completed");
  await act(async () => late({ ...running(), status: "failed" }));
  expect(hook.result.current.taskProgress[0].status).toBe("completed");
  expect(hook.onImported).toHaveBeenCalledTimes(1);
});

it("does not shorten retry delay when callbacks or batches change", async () => {
  vi.mocked(importApi.taskStatus).mockRejectedValue(new Error("offline"));
  const hook = await mount();
  hook.rerender({ callback: vi.fn() });
  await act(async () =>
    hook.result.current.trackTasks([{ id: "b", label: "B" }]),
  );
  await advance(1999);
  expect(
    vi.mocked(importApi.taskStatus).mock.calls.filter(([id]) => id === "a"),
  ).toHaveLength(1);
  await advance(6001);
  expect(hook.result.current.taskProgress[0].status).toBe("interrupted");
  await advance(20000);
  expect(
    vi.mocked(importApi.taskStatus).mock.calls.filter(([id]) => id === "a"),
  ).toHaveLength(5);
});

it("cancels a scheduled retry on unmount", async () => {
  vi.mocked(importApi.taskStatus).mockResolvedValue(running());
  const hook = await mount();
  hook.unmount();
  await advance(60000);
  expect(importApi.taskStatus).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});

it("treats mismatched task responses as failures instead of notifying success", async () => {
  vi.mocked(importApi.taskStatus).mockResolvedValue({
    ...running("someone-else"),
    status: "completed",
  });
  const hook = await mount();
  await advance(8000);
  expect(hook.result.current.taskProgress[0].status).toBe("interrupted");
  expect(hook.onImported).not.toHaveBeenCalled();
});
