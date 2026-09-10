"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { ImportTaskStatus } from "@/lib/api";
import {
  isImportTaskTerminal,
  startImportTaskPolling,
} from "./importTaskPolling";

interface TrackedTask {
  id: string;
  label: string;
}

/** Keep background imports observable even while the dialog is closed. */
export function useImportTaskTracking(onImported?: () => void) {
  const [batches, setBatches] = useState<TrackedTask[][]>([]);
  const [statuses, setStatuses] = useState<Record<string, ImportTaskStatus>>(
    {},
  );
  const statusesRef = useRef<Record<string, ImportTaskStatus>>({});
  const notifiedRef = useRef(new Set<TrackedTask[]>());
  const pollersRef = useRef(new Map<string, () => void>());
  const latest = useRef({ batches, onImported });
  useLayoutEffect(() => {
    latest.current = { batches, onImported };
  }, [batches, onImported]);

  const trackTasks = useCallback((tasks: TrackedTask[]) => {
    if (tasks.length) setBatches((current) => [...current, tasks]);
  }, []);

  useEffect(() => {
    const pollers = pollersRef.current;
    return () => {
      for (const cancel of pollers.values()) cancel();
      pollers.clear();
    };
  }, []);

  useEffect(() => {
    const updateStatus = (update: ImportTaskStatus) => {
      const next = { ...statusesRef.current, [update.task_id]: update };
      statusesRef.current = next;
      setStatuses(next);
      for (const batch of latest.current.batches) {
        if (
          notifiedRef.current.has(batch) ||
          !batch.every((task) => isImportTaskTerminal(next[task.id]?.status))
        )
          continue;
        notifiedRef.current.add(batch);
        if (batch.some((task) => next[task.id]?.status === "completed")) {
          latest.current.onImported?.();
        }
      }
    };
    for (const task of batches.flat()) {
      if (
        pollersRef.current.has(task.id) ||
        isImportTaskTerminal(statusesRef.current[task.id]?.status)
      )
        continue;
      pollersRef.current.set(
        task.id,
        startImportTaskPolling(task.id, updateStatus),
      );
    }
  }, [batches]);

  const taskProgress = batches.flat().map((task) => ({
    ...task,
    status: statuses[task.id]?.status,
    progress: statuses[task.id]?.progress,
    step: statuses[task.id]?.current_step,
    message: statuses[task.id]?.message,
  }));

  return { trackTasks, taskProgress };
}
