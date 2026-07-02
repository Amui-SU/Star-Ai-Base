"use client";

import type { VideoNoteBlock } from "@/lib/api";

interface VideoNoteBlockToolbarProps {
  block: VideoNoteBlock;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
  onConvert: (type: VideoNoteBlock["type"]) => void;
}

export default function VideoNoteBlockToolbar({
  block,
  onMoveUp,
  onMoveDown,
  onRemove,
  onConvert,
}: VideoNoteBlockToolbarProps) {
  return (
    <div className="video-note-block-toolbar" aria-label={`块工具 ${block.id}`}>
      <button type="button" onClick={onMoveUp} aria-label={`上移块 ${block.id}`}>
        ↑
      </button>
      <button
        type="button"
        onClick={onMoveDown}
        aria-label={`下移块 ${block.id}`}
      >
        ↓
      </button>
      <select
        aria-label={`转换块 ${block.id}`}
        value={block.type}
        onChange={(event) => onConvert(event.target.value)}
      >
        <option value="paragraph">段落</option>
        <option value="heading">标题</option>
        <option value="todo">待办</option>
        <option value="quote">引用</option>
        <option value="ai_summary">摘要</option>
      </select>
      <button type="button" onClick={onRemove} aria-label={`删除块 ${block.id}`}>
        ×
      </button>
    </div>
  );
}
