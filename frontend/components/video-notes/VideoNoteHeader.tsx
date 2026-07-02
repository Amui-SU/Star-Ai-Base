"use client";

import type { VideoNoteSaveStatus } from "./useVideoNoteAutosave";

interface VideoNoteHeaderProps {
  title: string;
  fullscreen: boolean;
  saveStatus: VideoNoteSaveStatus;
  knowledgeBaseName?: string;
  onClose?: () => void;
  onTitleChange: (title: string) => void;
  onToggleFullscreen: () => void;
}

const statusLabel: Record<VideoNoteSaveStatus, string> = {
  idle: "已同步",
  dirty: "待保存",
  saving: "保存中",
  saved: "已保存",
  error: "保存失败",
};

export default function VideoNoteHeader({
  title,
  fullscreen,
  knowledgeBaseName,
  saveStatus,
  onClose,
  onTitleChange,
  onToggleFullscreen,
}: VideoNoteHeaderProps) {
  return (
    <header className="video-note-header">
      <div className="video-note-title-group">
        <span className="video-note-kicker">{knowledgeBaseName ?? "视频笔记"}</span>
        <input
          aria-label="笔记标题"
          value={title}
          onChange={(event) => onTitleChange(event.target.value)}
        />
      </div>
      <div className="video-note-header-actions">
        <span className={`video-note-save-status ${saveStatus}`}>
          {statusLabel[saveStatus]}
        </span>
        <button type="button" onClick={onToggleFullscreen}>
          {fullscreen ? "半屏" : "全屏"}
        </button>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="关闭笔记">
            ×
          </button>
        )}
      </div>
    </header>
  );
}
