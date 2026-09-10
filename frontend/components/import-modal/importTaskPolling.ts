import { ApiError, importApi, type ImportTaskStatus } from "@/lib/api";

export const isImportTaskTerminal = (status?: string) =>
  status === "completed" || status === "failed" || status === "interrupted";

/** Own one task's requests and timers until completion or explicit disposal. */
export function startImportTaskPolling(
  taskId: string,
  onUpdate: (status: ImportTaskStatus) => void,
): () => void {
  let stopped = false;
  let failures = 0;
  let progress = 0;
  let controller: AbortController | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let requestTimer: ReturnType<typeof setTimeout> | undefined;
  const deadline = Date.now() + 2 * 60 * 60 * 1000;

  const stop = () => {
    stopped = true;
    clearTimeout(totalTimer);
    clearTimeout(retryTimer);
    clearTimeout(requestTimer);
    controller?.abort();
  };
  const interrupt = (message: string) => {
    if (stopped) return;
    stop();
    onUpdate({ task_id: taskId, status: "interrupted", progress, message });
  };
  const totalTimer = setTimeout(
    () => interrupt("任务跟踪已超时，请刷新查看结果或重新导入"),
    2 * 60 * 60 * 1000,
  );

  const poll = async () => {
    if (stopped) return;
    if (Date.now() >= deadline) {
      interrupt("任务跟踪已超时，请刷新查看结果或重新导入");
      return;
    }
    const requestController = new AbortController();
    controller = requestController;
    let abortListener: () => void = () => {};
    const aborted = new Promise<never>((_resolve, reject) => {
      abortListener = () =>
        reject(new DOMException("Polling aborted", "AbortError"));
      requestController.signal.addEventListener("abort", abortListener, {
        once: true,
      });
    });
    requestTimer = setTimeout(() => requestController.abort(), 10000);
    try {
      const update = await Promise.race([
        importApi.taskStatus(taskId, requestController.signal),
        aborted,
      ]);
      if (stopped) return;
      if (Date.now() >= deadline) {
        interrupt("任务跟踪已超时，请刷新查看结果或重新导入");
        return;
      }
      if (
        !update ||
        update.task_id !== taskId ||
        typeof update.status !== "string"
      ) {
        throw new Error("Invalid task status response");
      }
      failures = 0;
      progress = update.progress;
      if (isImportTaskTerminal(update.status)) stop();
      onUpdate(update);
    } catch (error) {
      if (stopped) return;
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        interrupt("无法继续查看任务，请重新登录或确认任务仍然存在");
      } else if (++failures >= 5) {
        interrupt("连续获取任务状态失败，请检查网络后刷新或重新导入");
      }
    } finally {
      clearTimeout(requestTimer);
      requestController.signal.removeEventListener("abort", abortListener);
      if (controller === requestController) controller = undefined;
    }
    if (!stopped) retryTimer = setTimeout(() => void poll(), 2000);
  };
  void poll();
  return stop;
}
