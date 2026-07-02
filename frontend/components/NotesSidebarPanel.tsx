"use client";

import { useState } from "react";

interface NotesSidebarPanelProps {
  onOpenVideoNotes?: () => void;
}

export default function NotesSidebarPanel({
  onOpenVideoNotes,
}: NotesSidebarPanelProps) {
  const [note, setNote] = useState("");

  return (
    <div className="sidebar-tool-panel notes-sidebar-panel">
      <div className="sidebar-tool-head">
        <div>
          <span className="sidebar-tool-kicker">学习</span>
          <h2>笔记</h2>
        </div>
        {onOpenVideoNotes && (
          <button
            type="button"
            className="sidebar-tool-action"
            onClick={onOpenVideoNotes}
          >
            打开视频笔记库
          </button>
        )}
      </div>
      <textarea
        aria-label="学习笔记"
        className="notes-sidebar-editor"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="写下这次学习的要点"
      />
    </div>
  );
}
