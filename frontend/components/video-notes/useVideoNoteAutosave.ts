"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { VideoNote, VideoNoteBlock, VideoNoteSaveRequest } from "@/lib/api";

export type VideoNoteSaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

interface UseVideoNoteAutosaveOptions {
  note: VideoNote | null;
  title: string;
  blocks: VideoNoteBlock[];
  tags: string[];
  exportFilenameTemplate?: string | null;
  save: (noteId: number, payload: VideoNoteSaveRequest) => Promise<VideoNote>;
  enabled?: boolean;
  delayMs?: number;
}

function buildPayload({
  title,
  blocks,
  tags,
  exportFilenameTemplate,
}: Pick<
  UseVideoNoteAutosaveOptions,
  "title" | "blocks" | "tags" | "exportFilenameTemplate"
>): VideoNoteSaveRequest {
  return {
    title,
    blocks,
    tags,
    export_filename_template: exportFilenameTemplate ?? undefined,
  };
}

export function useVideoNoteAutosave({
  note,
  title,
  blocks,
  tags,
  exportFilenameTemplate,
  save,
  enabled = true,
  delayMs = 800,
}: UseVideoNoteAutosaveOptions) {
  const [status, setStatus] = useState<VideoNoteSaveStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  const lastSavedKey = useRef("");
  const latestPayload = useMemo(
    () => buildPayload({ title, blocks, tags, exportFilenameTemplate }),
    [title, blocks, tags, exportFilenameTemplate],
  );
  const latestKey = useMemo(() => JSON.stringify(latestPayload), [latestPayload]);

  useEffect(() => {
    let nextStatus: VideoNoteSaveStatus = "idle";
    if (!note) {
      lastSavedKey.current = "";
    } else {
      lastSavedKey.current = JSON.stringify(
        buildPayload({
          title: note.title,
          blocks: note.blocks,
          tags: note.tags,
          exportFilenameTemplate: note.export_filename_template,
        }),
      );
      nextStatus = "idle";
    }
    const timer = window.setTimeout(() => setStatus(nextStatus), 0);
    return () => window.clearTimeout(timer);
  }, [note]);

  const runSave = useCallback(async () => {
    if (!enabled || !note || latestKey === lastSavedKey.current) {
      return;
    }
    setStatus("saving");
    setError(null);
    try {
      await save(note.id, latestPayload);
      lastSavedKey.current = latestKey;
      setStatus("saved");
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error("保存失败"));
      setStatus("error");
    }
  }, [enabled, latestKey, latestPayload, note, save]);

  useEffect(() => {
    if (!enabled || !note || latestKey === lastSavedKey.current) return;
    setStatus("dirty");
    const timer = window.setTimeout(() => {
      void runSave();
    }, delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, enabled, latestKey, note, runSave]);

  return {
    status,
    error,
    flush: runSave,
  };
}
