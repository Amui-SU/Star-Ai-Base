"use client";

import { useState } from "react";

import type { VideoNoteExportResponse } from "@/lib/api";

interface VideoNoteToolRailProps {
  aiPanelCollapsed: boolean;
  canExport: boolean;
  exported: VideoNoteExportResponse | null;
  exportFilenameTemplate: string;
  exporting: boolean;
  onAddParagraph: () => void;
  onAddTodo: () => void;
  onExportMarkdown: () => Promise<VideoNoteExportResponse | null>;
  onExportFilenameTemplateChange: (value: string) => void;
  onToggleAiPanel: () => void;
}

export default function VideoNoteToolRail({
  aiPanelCollapsed,
  canExport,
  exported,
  exportFilenameTemplate,
  exporting,
  onAddParagraph,
  onAddTodo,
  onExportMarkdown,
  onExportFilenameTemplateChange,
  onToggleAiPanel,
}: VideoNoteToolRailProps) {
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  const getExportedMarkdown = async () => {
    if (exported) return exported;
    return onExportMarkdown();
  };

  const handleCopyMarkdown = async () => {
    setExportStatus("正在准备 Markdown");
    const nextExport = await getExportedMarkdown();
    if (!nextExport) {
      setExportStatus("没有可导出的笔记");
      return;
    }
    await navigator.clipboard.writeText(nextExport.markdown);
    setExportStatus("已复制 Markdown");
  };

  const handleDownloadMarkdown = async () => {
    setExportStatus("正在准备 Markdown");
    const nextExport = await getExportedMarkdown();
    if (!nextExport) {
      setExportStatus("没有可导出的笔记");
      return;
    }
    const blob = new Blob([nextExport.markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = nextExport.filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setExportStatus(null);
    setExportMenuOpen(false);
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
      <button
        type="button"
        className="video-note-tool-button"
        onClick={onToggleAiPanel}
        aria-pressed={!aiPanelCollapsed}
        aria-label={aiPanelCollapsed ? "展开 AI 工具" : "折叠 AI 工具"}
        data-tooltip={aiPanelCollapsed ? "展开 AI 工具" : "折叠 AI 工具"}
      >
        <AiIcon />
      </button>
      <div className="video-note-tool-menu-anchor">
        <button
          type="button"
          className="video-note-tool-button"
          onClick={() => {
            setExportMenuOpen((value) => !value);
            setExportStatus(null);
          }}
          disabled={!canExport || exporting}
          aria-label="导出 Markdown"
          data-tooltip={exporting ? "正在导出" : "导出 Markdown"}
        >
          <DownloadIcon />
        </button>
        {exportMenuOpen && (
          <div
            className="video-note-export-menu"
            role="menu"
            aria-label="Markdown 导出操作"
          >
            <div className="video-note-export-popover-head">
              <strong>{exported?.filename ?? "导出 Markdown"}</strong>
              <button
                type="button"
                onClick={() => setExportMenuOpen(false)}
                aria-label="关闭导出菜单"
              >
                ×
              </button>
            </div>
            <label className="video-note-export-field">
              <span>导出文件名</span>
              <input
                className="video-note-export-template-input"
                type="text"
                value={exportFilenameTemplate}
                onChange={(event) => {
                  onExportFilenameTemplateChange(event.target.value);
                  setExportStatus(null);
                }}
                placeholder="{{title}}.md"
              />
            </label>
            <button
              type="button"
              className="video-note-export-action"
              onClick={() => void handleCopyMarkdown()}
              disabled={exporting}
            >
              <CopyIcon />
              <span>复制 Markdown</span>
            </button>
            <button
              type="button"
              className="video-note-export-action"
              onClick={() => void handleDownloadMarkdown()}
              disabled={exporting}
            >
              <DownloadIcon />
              <span>下载 Markdown 文件</span>
            </button>
            {exportStatus && (
              <p className="video-note-export-status">{exportStatus}</p>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}

function AiIcon() {
  return (
    <span className="video-note-tool-icon-text" aria-hidden="true">
      AI
    </span>
  );
}

function CopyIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      focusable="false"
    >
      <rect x="8" y="8" width="10" height="10" rx="2" />
      <path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      focusable="false"
    >
      <path d="M12 3v11" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 20h14" />
    </svg>
  );
}
