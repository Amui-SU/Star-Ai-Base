import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const videoNoteStyles = readFileSync(
  resolve(process.cwd(), "app/styles/video-notes.css"),
  "utf8",
);

describe("video note styles", () => {
  it("hides the visible editor scrollbar while keeping Vditor content overflow external", () => {
    expect(videoNoteStyles).toMatch(
      /\.video-note-markdown-editor\s*{[^}]*scrollbar-width:\s*none/s,
    );
    expect(videoNoteStyles).toContain(
      ".video-note-markdown-editor::-webkit-scrollbar",
    );
    expect(videoNoteStyles).toContain(".video-note-vditor.vditor");
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-content,[\s\S]*?overflow:\s*visible/s,
    );
  });
});
