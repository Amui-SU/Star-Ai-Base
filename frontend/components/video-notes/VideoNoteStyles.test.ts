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

  it("keeps AI tools from creating horizontal scroll and adapts collapse icon direction", () => {
    expect(videoNoteStyles).toMatch(
      /\.video-note-side-panel\s*{[^}]*overflow-x:\s*hidden/s,
    );
    expect(videoNoteStyles).toContain(".video-note-ai-collapse .chevron-left");
    expect(videoNoteStyles).toContain(".video-note-ai-collapse .chevron-down");
    expect(videoNoteStyles).toMatch(
      /\.video-note-side-panel \.video-note-ai-collapse::after\s*{[^}]*right:\s*calc\(100% \+ 10px\)/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-ai-collapse \.chevron-left\s*{[\s\S]*?display:\s*none/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-ai-collapse \.chevron-down\s*{[\s\S]*?display:\s*block/s,
    );
  });
});
