"use client";

interface VideoNoteToolRailProps {
  onAddParagraph: () => void;
  onAddTodo: () => void;
}

export default function VideoNoteToolRail({
  onAddParagraph,
  onAddTodo,
}: VideoNoteToolRailProps) {
  return (
    <nav className="video-note-tool-rail" aria-label="笔记工具">
      <button type="button" onClick={onAddParagraph} title="添加段落">
        ¶
      </button>
      <button type="button" onClick={onAddTodo} title="添加待办">
        ✓
      </button>
    </nav>
  );
}
