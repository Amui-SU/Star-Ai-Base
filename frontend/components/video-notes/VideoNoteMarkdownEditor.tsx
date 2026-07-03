"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

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

export default function VideoNoteMarkdownEditor({
  blocks,
  onChange,
}: VideoNoteMarkdownEditorProps) {
  const editorId = `video-note-vditor-${useId().replace(/:/g, "")}`;
  const markdown = useMemo(() => blocksToMarkdown(blocks), [blocks]);
  const editorRef = useRef<VditorInstance | null>(null);
  const blocksRef = useRef(blocks);
  const onChangeRef = useRef(onChange);
  const lastMarkdownRef = useRef(markdown);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    blocksRef.current = blocks;
  }, [blocks]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

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
            lastMarkdownRef.current = value;
            onChangeRef.current(
              markdownToVideoNoteBlocks(value, blocksRef.current),
            );
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
  }, [editorId]);

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
      className="video-note-markdown-editor"
      aria-label="Markdown 笔记编辑器"
    >
      <div id={editorId} className="video-note-vditor" />
    </div>
  );
}
