"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { importApi, type ImportTaskStatus } from "@/lib/api";

interface TrackedTask {
  id: string;
  label: string;
}

const isTerminal = (status?: string) =>
  status === "completed" || status === "failed" || status === "interrupted";

/** Keep background imports observable even while the dialog is closed. */
export function useImportTaskTracking(onImported?: () => void) {
  const [batches, setBatches] = useState<TrackedTask[][]>([]);
  const [statuses, setStatuses] = useState<Record<string, ImportTaskStatus>>(
    {},
  );
  const statusesRef = useRef<Record<string, ImportTaskStatus>>({});
  const notifiedRef = useRef(new Set<string>());

  const trackTasks = useCallback((tasks: TrackedTask[]) => {
    if (tasks.length) setBatches((current) => [...current, tasks]);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timers = new Set<number>();
    const poll = async (task: TrackedTask) => {
      if (isTerminal(statusesRef.current[task.id]?.status)) return;
      let update: ImportTaskStatus | null = null;
      try {
        update = await importApi.taskStatus(task.id);
      } catch {
        // A transient error retries this task without holding up other tasks.
      }
      if (cancelled) return;
      const next = { ...statusesRef.current };
      if (update?.task_id === task.id) next[task.id] = update;
      statusesRef.current = next;
      setStatuses(next);
      for (const batch of batches) {
        const key = batch[0].id;
        if (
          notifiedRef.current.has(key) ||
          !batch.every((task) => isTerminal(next[task.id]?.status))
        )
          continue;
        notifiedRef.current.add(key);
        if (batch.some((task) => next[task.id]?.status === "completed")) {
          onImported?.();
        }
      }
      if (!cancelled && !isTerminal(next[task.id]?.status)) {
        const timer = window.setTimeout(() => {
          timers.delete(timer);
          void poll(task);
        }, 2000);
        timers.add(timer);
      }
    };
    for (const task of batches.flat()) void poll(task);
    return () => {
      cancelled = true;
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [batches, onImported]);

  const taskProgress = batches.flat().map((task) => ({
    ...task,
    status: statuses[task.id]?.status,
    progress: statuses[task.id]?.progress,
    step: statuses[task.id]?.current_step,
    message: statuses[task.id]?.message,
  }));

  return { trackTasks, taskProgress };
}
