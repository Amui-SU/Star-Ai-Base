"use client";

import { useState } from "react";

import type { VideoNoteExportResponse } from "@/lib/api";

interface VideoNoteToolRailProps {
  canExport: boolean;
  exported: VideoNoteExportResponse | null;
  exporting: boolean;
  onAddParagraph: () => void;
  onAddTodo: () => void;
  onExportMarkdown: () => Promise<void>;
}

export default function VideoNoteToolRail({
  canExport,
  exported,
  exporting,
  onAddParagraph,
  onAddTodo,
  onExportMarkdown,
}: VideoNoteToolRailProps) {
  const [exportPreviewOpen, setExportPreviewOpen] = useState(false);

  const handleExport = async () => {
    await onExportMarkdown();
    setExportPreviewOpen(true);
  };

  return (
    <nav className="video-note-tool-rail" aria-label="笔记工具">
      <button
        type="button"
        className="video-note-tool-button"
        onClick={onAddParagraph}
        aria-label="添加段落"
        data-tooltip="添加段落"
      >
        <span aria-hidden="true">¶</span>
      </button>
      <button
        type="button"
        className="video-note-tool-button"
        onClick={onAddTodo}
        aria-label="添加待办"
        data-tooltip="添加待办"
      >
        <span aria-hidden="true">✓</span>
      </button>
      <div className="video-note-tool-spacer" aria-hidden="true" />
      <button
        type="button"
        className="video-note-tool-button"
        onClick={() => void handleExport()}
        disabled={!canExport || exporting}
        aria-label="导出 Markdown"
        data-tooltip={exporting ? "正在导出" : "导出 Markdown"}
      >
        <span aria-hidden="true">MD</span>
      </button>
      {exportPreviewOpen && exported && (
        <div className="video-note-export-popover" role="status">
          <div className="video-note-export-popover-head">
            <strong>{exported.filename}</strong>
            <button
              type="button"
              onClick={() => setExportPreviewOpen(false)}
              aria-label="关闭导出预览"
            >
              ×
            </button>
          </div>
          <textarea
            readOnly
            value={exported.markdown}
            aria-label="Markdown 预览"
          />
        </div>
      )}
    </nav>
  );
}
