"use client";

import type { VideoNoteAiResponse } from "@/lib/api";

interface VideoNoteAiPanelProps {
  collapsed: boolean;
  loading: boolean;
  canUndoAiEdit: boolean;
  message: string | null;
  onGenerateSummary: () => Promise<VideoNoteAiResponse | void>;
  onGenerateQuestions: () => Promise<VideoNoteAiResponse | void>;
  onToggleCollapsed: () => void;
  onUndoAiEdit: () => void;
}

export default function VideoNoteAiPanel({
  collapsed,
  loading,
  canUndoAiEdit,
  message,
  onGenerateSummary,
  onGenerateQuestions,
  onToggleCollapsed,
  onUndoAiEdit,
}: VideoNoteAiPanelProps) {
  if (collapsed) {
    return (
      <section className="video-note-ai-panel collapsed" aria-label="AI 工具">
        <button
          type="button"
          className="video-note-ai-expand"
          onClick={onToggleCollapsed}
          aria-label="展开 AI 工具"
          data-tooltip="展开 AI 工具"
        >
          AI
        </button>
      </section>
    );
  }

  return (
    <section className="video-note-ai-panel">
      <div className="video-note-ai-panel-head">
        <div>
          <span className="video-note-kicker">AI</span>
          <h3>协作编辑</h3>
        </div>
        <button
          type="button"
          className="video-note-ai-collapse"
          onClick={onToggleCollapsed}
          aria-label="折叠 AI 工具"
          data-tooltip="折叠 AI 工具"
        >
          ›
        </button>
      </div>
      <div className="video-note-ai-actions">
        <button
          type="button"
          onClick={() => void onGenerateSummary()}
          disabled={loading}
        >
          生成摘要
        </button>
        <button
          type="button"
          onClick={() => void onGenerateQuestions()}
          disabled={loading}
        >
          生成问题
        </button>
        <button type="button" onClick={onUndoAiEdit} disabled={!canUndoAiEdit}>
          撤销 AI 编辑
        </button>
      </div>
      {message && <p>{message}</p>}
    </section>
  );
}
