import { describe, expect, it } from "vitest";

import { readStylesheetWithLocalImports } from "./testStyles";

const stylesheet = readStylesheetWithLocalImports();

describe("AI service key modal layout", () => {
  it("keeps the desktop modal within the viewport and lets columns shrink", () => {
    expect(stylesheet).toMatch(
      /\.modal-card\.api-accounts-panel\s*\{[^}]*width:\s*min\(1120px,\s*calc\(100vw - 24px\)\);[^}]*max-height:\s*min\(92dvh,\s*860px\);[^}]*overflow:\s*hidden;/s,
    );
    expect(stylesheet).toMatch(
      /\.api-accounts-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*0\.9fr\)\s*minmax\(0,\s*1\.1fr\);[^}]*overflow:\s*hidden;/s,
    );
  });

  it("switches the key modal to a single scrollable column before narrow screens can crop it", () => {
    expect(stylesheet).toMatch(
      /@media \(max-width:\s*860px\)\s*\{[\s\S]*?\.api-accounts-panel\s*\{[^}]*width:\s*calc\(100vw - 20px\);[\s\S]*?\.api-accounts-layout\s*\{[^}]*grid-template-columns:\s*1fr;[^}]*overflow-y:\s*auto;[\s\S]*?\}/s,
    );
  });
});

describe("workspace header layering", () => {
  it("keeps the user menu above chat model controls", () => {
    expect(stylesheet).toMatch(
      /\.workspace-topbar\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*140;/s,
    );
    expect(stylesheet).toMatch(/\.modal-backdrop\s*\{[^}]*z-index:\s*220;/s);
  });
});
