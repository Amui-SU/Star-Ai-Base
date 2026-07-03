"use client";

import type { VideoNoteAiResponse } from "@/lib/api";

interface VideoNoteAiPanelProps {
  collapsed: boolean;
  loading: boolean;
  canUndoAiEdit: boolean;
  message: string | null;
  onCollapse: () => void;
  onGenerateSummary: () => Promise<VideoNoteAiResponse | void>;
  onGenerateQuestions: () => Promise<VideoNoteAiResponse | void>;
  onGenerateTimestamps: () => Promise<VideoNoteAiResponse | void>;
  onUndoAiEdit: () => void;
}

export default function VideoNoteAiPanel({
  collapsed,
  loading,
  canUndoAiEdit,
  message,
  onCollapse,
  onGenerateSummary,
  onGenerateQuestions,
  onGenerateTimestamps,
  onUndoAiEdit,
}: VideoNoteAiPanelProps) {
  if (collapsed) {
    return null;
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
          aria-label="折叠 AI 工具"
          data-tooltip="折叠 AI 工具"
          onClick={onCollapse}
        >
          <svg className="chevron-left" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m15 5-7 7 7 7" />
          </svg>
          <svg className="chevron-down" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
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
        <button
          type="button"
          onClick={() => void onGenerateTimestamps()}
          disabled={loading}
        >
          生成时间戳
        </button>
        <button type="button" onClick={onUndoAiEdit} disabled={!canUndoAiEdit}>
          撤销 AI 编辑
        </button>
      </div>
      {message && (
        <p className="video-note-ai-status" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
