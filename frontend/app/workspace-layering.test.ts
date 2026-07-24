import { describe, expect, it } from "vitest";

import { readStylesheetWithLocalImports } from "./testStyles";

const stylesheet = readStylesheetWithLocalImports();

describe("workspace header layering", () => {
  it("keeps the user menu above chat model controls", () => {
    expect(stylesheet).toMatch(
      /\.workspace-topbar\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*140;/s,
    );
    expect(stylesheet).toMatch(/\.modal-backdrop\s*\{[^}]*z-index:\s*220;/s);
  });
});
