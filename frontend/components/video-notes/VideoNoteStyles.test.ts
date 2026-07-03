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

  it("centers AI operation status inside its own side-panel area", () => {
    expect(videoNoteStyles).toMatch(
      /\.video-note-ai-status-wrap\s*{[^}]*place-items:\s*center/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-ai-status-wrap\s*{[^}]*min-height:\s*116px/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-ai-status\s*{[^}]*text-align:\s*center/s,
    );
  });

  it("keeps the mobile AI panel compact and centered", () => {
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?grid-template-rows:\s*minmax\(0,\s*1fr\)\s*minmax\(184px,\s*22dvh\)/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-side-panel\s*{[\s\S]*?align-content:\s*center/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-side-panel\s*{[\s\S]*?justify-items:\s*center/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-ai-panel\s*{[\s\S]*?width:\s*min\(100%,\s*340px\)/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-ai-panel\s*{[\s\S]*?max-width:\s*340px/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(max-width: 1024px\)[\s\S]*?\.video-note-ai-collapse\s*{[\s\S]*?position:\s*static/s,
    );
    const mobileCss = videoNoteStyles.split("@media (max-width: 1024px)")[1];
    expect(mobileCss).not.toContain("calc(100vw - 48px)");
  });

  it("keeps the mobile editor surface centered without horizontal overflow traps", () => {
    const mobileCss = videoNoteStyles.split("@media (max-width: 1024px)")[1];

    expect(mobileCss).toMatch(
      /\.video-note-editor-shell\s*{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/s,
    );
    expect(mobileCss).toMatch(
      /\.video-note-editor-shell\s*{[\s\S]*?grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)/s,
    );
    expect(mobileCss).toMatch(
      /\.video-note-tool-rail\s*{[\s\S]*?flex-direction:\s*row/s,
    );
    expect(mobileCss).toMatch(
      /\.video-note-markdown-editor\s*{[\s\S]*?width:\s*100%/s,
    );
    expect(mobileCss).toMatch(
      /\.video-note-tool-button::after,[\s\S]*?\.video-note-ai-expand::after\s*{[\s\S]*?display:\s*none/s,
    );
  });

  it("wraps long Vditor note content instead of creating an inner horizontal scrollbar", () => {
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-ir pre\.vditor-reset,[\s\S]*?\.video-note-vditor \.vditor-ir \.vditor-reset\s*{[\s\S]*?overflow-wrap:\s*anywhere/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-ir pre\.vditor-reset,[\s\S]*?\.video-note-vditor \.vditor-ir \.vditor-reset\s*{[\s\S]*?white-space:\s*pre-wrap/s,
    );
  });
});
