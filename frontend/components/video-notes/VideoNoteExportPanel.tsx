"use client";

import type { VideoNoteExportResponse } from "@/lib/api";

interface VideoNoteExportPanelProps {
  exported: VideoNoteExportResponse | null;
  exporting: boolean;
  onExportMarkdown: () => Promise<void>;
}

export default function VideoNoteExportPanel({
  exported,
  exporting,
  onExportMarkdown,
}: VideoNoteExportPanelProps) {
  return (
    <section className="video-note-export-panel">
      <div>
        <span className="video-note-kicker">导出</span>
        <h3>Markdown</h3>
      </div>
      <button type="button" onClick={() => void onExportMarkdown()} disabled={exporting}>
        导出 Markdown
      </button>
      {exported && (
        <div className="video-note-export-result">
          <strong>{exported.filename}</strong>
          <textarea readOnly value={exported.markdown} aria-label="Markdown 预览" />
        </div>
      )}
    </section>
  );
}
