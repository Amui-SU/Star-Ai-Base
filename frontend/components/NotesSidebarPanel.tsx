"use client";

import { useState } from "react";

export default function NotesSidebarPanel() {
  const [note, setNote] = useState("");

  return (
    <div className="sidebar-tool-panel notes-sidebar-panel">
      <div className="sidebar-tool-head">
        <div>
          <span className="sidebar-tool-kicker">学习</span>
          <h2>笔记</h2>
        </div>
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
