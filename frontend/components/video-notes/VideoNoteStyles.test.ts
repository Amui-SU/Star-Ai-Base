import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesRoot = resolve(process.cwd(), "app/styles");

const readStylesheet = (relativePath: string, baseDir = stylesRoot): string => {
  const filePath = resolve(baseDir, relativePath);
  const source = readFileSync(filePath, "utf8");
  return source.replace(
    /^@import\s+"\.\/([^"]+)";/gm,
    (_match, importPath: string) =>
      readStylesheet(importPath, dirname(filePath)),
  );
};

const videoNoteStyles = readStylesheet("video-notes.css");

describe("video note styles", () => {
  it("lets the desktop note drawer cover the app top bar for full viewport height", () => {
    const desktopCss = videoNoteStyles.split("@media (max-width: 1024px)")[0];

    expect(desktopCss).toMatch(
      /\.video-note-drawer\s*{[^}]*position:\s*fixed/s,
    );
    expect(desktopCss).toMatch(
      /\.video-note-drawer\s*{[^}]*inset:\s*0\s+auto\s+0\s+0/s,
    );
    expect(desktopCss).toMatch(/\.video-note-drawer\s*{[^}]*z-index:\s*180/s);
    expect(desktopCss).toMatch(/\.video-note-drawer\s*{[^}]*height:\s*100dvh/s);
  });

  it("gives light-mode note shell surfaces their own visual weight", () => {
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-list-panel,[\s\S]*?html\.light \.video-note-side-panel\s*{[\s\S]*?background:\s*#ded4c6/s,
    );
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-header\s*{[\s\S]*?background:\s*#ded4c6/s,
    );
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-header\s*{[\s\S]*?border-bottom-color:\s*#c8b89f/s,
    );
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-tool-rail\s*{[\s\S]*?background:\s*#ded4c6/s,
    );
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-side-panel\s*{[\s\S]*?border-left-color:\s*#c8b89f/s,
    );
  });

  it("pins the Vditor toolbar while keeping note text and rail tooltips clear", () => {
    expect(videoNoteStyles).toMatch(
      /\.video-note-tool-rail\s*{[\s\S]*?z-index:\s*40/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-toolbar\s*{[\s\S]*?position:\s*sticky/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-toolbar\s*{[\s\S]*?top:\s*0/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-toolbar\s*{[\s\S]*?flex:\s*0 0 auto/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-content\s*{[\s\S]*?margin-top:\s*8px/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-toolbar \.vditor-tooltipped\s*{[\s\S]*?overflow:\s*visible/s,
    );
    expect(videoNoteStyles).toMatch(
      /\.video-note-vditor \.vditor-toolbar \.vditor-tooltipped:hover::before,[\s\S]*?\.video-note-vditor \.vditor-toolbar \.vditor-tooltipped:focus::after\s*{[\s\S]*?opacity:\s*1\s*!important/s,
    );
  });

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

  it("removes the desktop AI panel column when AI tools collapse", () => {
    const desktopCss = videoNoteStyles.split("@media (max-width: 1024px)")[0];

    expect(desktopCss).not.toMatch(
      /\.video-note-drawer\.ai-collapsed\s*{[^}]*max-width:/s,
    );
    expect(desktopCss).toMatch(
      /\.video-note-workspace\.ai-collapsed\s*{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s,
    );
    expect(desktopCss).toMatch(
      /\.video-note-side-panel\.collapsed\s*{[^}]*display:\s*none/s,
    );
  });

  it("slightly deepens the light-mode editor surface", () => {
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-markdown-editor,[\s\S]*?html\.light \.video-note-vditor\.vditor\s*{[\s\S]*?background:\s*#f1eadf/s,
    );
    expect(videoNoteStyles).toMatch(
      /html\.light \.video-note-vditor \.vditor-toolbar,[\s\S]*?html\.light \.video-note-vditor \.vditor-ir \.vditor-reset\s*{[\s\S]*?background:\s*#f1eadf/s,
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
    expect(mobileCss).not.toMatch(/\.video-note-tool-button::after/);
  });

  it("does not hide editor tooltips solely because the viewport is narrow", () => {
    expect(videoNoteStyles).not.toMatch(
      /@media \(max-width: 768px\)[\s\S]{0,600}\.video-note-vditor \.vditor-toolbar \.vditor-tooltipped:hover::after,[\s\S]{0,180}display:\s*none\s*!important/s,
    );
    expect(videoNoteStyles).not.toMatch(
      /@media \(max-width: 768px\)[\s\S]{0,600}\.video-note-tool-button::after,[\s\S]{0,180}display:\s*none/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(hover: none\) and \(pointer: coarse\)[\s\S]*?\.video-note-vditor \.vditor-toolbar \.vditor-tooltipped:hover::after,[\s\S]*?display:\s*none\s*!important/s,
    );
    expect(videoNoteStyles).toMatch(
      /@media \(hover: none\) and \(pointer: coarse\)[\s\S]*?\.video-note-tool-button::after,[\s\S]*?display:\s*none/s,
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
