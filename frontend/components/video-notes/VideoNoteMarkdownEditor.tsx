"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import type { VideoNoteBlock } from "@/lib/api";
import {
  blocksToMarkdown,
  markdownToVideoNoteBlocks,
} from "./videoNoteMarkdownAdapter";

interface VideoNoteMarkdownEditorProps {
  blocks: VideoNoteBlock[];
  onChange: (blocks: VideoNoteBlock[]) => void;
}

type VditorInstance = import("vditor").default;
type UndoRedoKeyboardEvent = Pick<
  KeyboardEvent,
  | "altKey"
  | "ctrlKey"
  | "defaultPrevented"
  | "key"
  | "metaKey"
  | "preventDefault"
  | "shiftKey"
>;

export default function VideoNoteMarkdownEditor({
  blocks,
  onChange,
}: VideoNoteMarkdownEditorProps) {
  const editorId = `video-note-vditor-${useId().replace(/:/g, "")}`;
  const markdown = useMemo(() => blocksToMarkdown(blocks), [blocks]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<VditorInstance | null>(null);
  const blocksRef = useRef(blocks);
  const onChangeRef = useRef(onChange);
  const lastMarkdownRef = useRef(markdown);
  const undoStackRef = useRef<string[]>([]);
  const redoStackRef = useRef<string[]>([]);
  const applyingHistoryRef = useRef(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    blocksRef.current = blocks;
  }, [blocks]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const applyMarkdownValue = useCallback((value: string) => {
    const editor = editorRef.current;
    if (editor?.getValue() !== value) {
      editor?.setValue(value);
    }
    lastMarkdownRef.current = value;
    onChangeRef.current(markdownToVideoNoteBlocks(value, blocksRef.current));
  }, []);

  const recordMarkdownInput = useCallback((value: string) => {
    if (!applyingHistoryRef.current && lastMarkdownRef.current !== value) {
      undoStackRef.current.push(lastMarkdownRef.current);
      if (undoStackRef.current.length > 100) {
        undoStackRef.current.shift();
      }
      redoStackRef.current = [];
    }
    lastMarkdownRef.current = value;
    onChangeRef.current(markdownToVideoNoteBlocks(value, blocksRef.current));
  }, []);

  const recordPendingEditorValue = useCallback(() => {
    const editor = editorRef.current;
    if (!editor || applyingHistoryRef.current) return;
    const value = editor.getValue();
    if (lastMarkdownRef.current === value) return;
    recordMarkdownInput(value);
  }, [recordMarkdownInput]);

  const undoMarkdown = useCallback(() => {
    const previous = undoStackRef.current.pop();
    if (previous === undefined) return;
    const editor = editorRef.current;
    const current = editor?.getValue() ?? lastMarkdownRef.current;
    redoStackRef.current.push(current);
    applyingHistoryRef.current = true;
    applyMarkdownValue(previous);
    applyingHistoryRef.current = false;
  }, [applyMarkdownValue]);

  const redoMarkdown = useCallback(() => {
    const next = redoStackRef.current.pop();
    if (next === undefined) return;
    const editor = editorRef.current;
    const current = editor?.getValue() ?? lastMarkdownRef.current;
    undoStackRef.current.push(current);
    applyingHistoryRef.current = true;
    applyMarkdownValue(next);
    applyingHistoryRef.current = false;
  }, [applyMarkdownValue]);

  const handleUndoRedoShortcut = useCallback(
    (event: UndoRedoKeyboardEvent) => {
      if (event.defaultPrevented) return;
      const isModifierPressed = event.ctrlKey || event.metaKey;
      if (!isModifierPressed || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        recordPendingEditorValue();
        if (undoStackRef.current.length === 0) return;
        event.preventDefault();
        undoMarkdown();
        return;
      }
      if (key === "y" || (key === "z" && event.shiftKey)) {
        if (redoStackRef.current.length === 0) return;
        event.preventDefault();
        redoMarkdown();
      }
    },
    [recordPendingEditorValue, redoMarkdown, undoMarkdown],
  );

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    handleUndoRedoShortcut(event);
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleNativeKeyDown = (event: KeyboardEvent) => {
      handleUndoRedoShortcut(event);
    };
    container.addEventListener("keydown", handleNativeKeyDown, true);
    return () => {
      container.removeEventListener("keydown", handleNativeKeyDown, true);
    };
  }, [handleUndoRedoShortcut]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleNativeInput = () => {
      const editor = editorRef.current;
      if (!editor || applyingHistoryRef.current) return;
      recordMarkdownInput(editor.getValue());
    };
    container.addEventListener("input", handleNativeInput, true);
    return () => {
      container.removeEventListener("input", handleNativeInput, true);
    };
  }, [recordMarkdownInput]);

  useEffect(() => {
    let cancelled = false;

    async function mountEditor() {
      try {
        const { default: Vditor } = await import("vditor");
        if (cancelled) return;

        editorRef.current = new Vditor(editorId, {
          cache: { enable: false },
          height: "100%",
          minHeight: 420,
          mode: "ir",
          placeholder: "开始记录这段视频里的观点、问题和行动项...",
          theme: document.documentElement.classList.contains("light")
            ? "classic"
            : "dark",
          toolbar: [
            "headings",
            "bold",
            "italic",
            "strike",
            "|",
            "list",
            "ordered-list",
            "check",
            "quote",
            "code",
            "table",
            "|",
            "undo",
            "redo",
            "|",
            "preview",
            "fullscreen",
          ],
          value: lastMarkdownRef.current,
          input(value) {
            recordMarkdownInput(value);
          },
        });
      } catch {
        if (!cancelled) setLoadError(true);
      }
    }

    void mountEditor();

    return () => {
      cancelled = true;
      editorRef.current?.destroy();
      editorRef.current = null;
    };
  }, [editorId, recordMarkdownInput]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) {
      lastMarkdownRef.current = markdown;
      return;
    }
    if (lastMarkdownRef.current === markdown) return;
    if (editor.getValue() !== markdown) {
      editor.setValue(markdown, true);
    }
    lastMarkdownRef.current = markdown;
    undoStackRef.current = [];
    redoStackRef.current = [];
  }, [markdown]);

  if (loadError) {
    return (
      <div className="video-note-markdown-editor error">
        编辑器加载失败，请稍后重试。
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="video-note-markdown-editor"
      aria-label="Markdown 笔记编辑器"
      onKeyDown={handleKeyDown}
    >
      <div id={editorId} className="video-note-vditor" />
    </div>
  );
}
