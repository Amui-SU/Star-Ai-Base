"use client";

import type { VideoNoteAiResponse } from "@/lib/api";

interface VideoNoteAiPanelProps {
  collapsed: boolean;
  loading: boolean;
  canUndoAiEdit: boolean;
  message: string | null;
  onGenerateSummary: () => Promise<VideoNoteAiResponse | void>;
  onGenerateQuestions: () => Promise<VideoNoteAiResponse | void>;
  onUndoAiEdit: () => void;
}

export default function VideoNoteAiPanel({
  collapsed,
  loading,
  canUndoAiEdit,
  message,
  onGenerateSummary,
  onGenerateQuestions,
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
