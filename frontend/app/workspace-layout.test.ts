import { describe, expect, it } from "vitest";

import { readStylesheetWithLocalImports } from "./testStyles";

const stylesheet = readStylesheetWithLocalImports();

function ruleFor(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = stylesheet.match(new RegExp(`${escaped}\\s*\\{[^}]*\\}`, "s"));
  return match?.[0] ?? "";
}

describe("workspace desktop layout", () => {
  it("uses an edge-to-edge workspace surface instead of an outer card", () => {
    const appMain = ruleFor(".app-main");
    const workspaceCard = ruleFor(".workspace-card");
    const lightWorkspaceCard = ruleFor("html.light .workspace-card");

    expect(appMain).toContain("padding: 0;");
    expect(workspaceCard).toContain("border: 0;");
    expect(workspaceCard).toContain("border-radius: 0;");
    expect(workspaceCard).toContain("box-shadow: none;");
    expect(lightWorkspaceCard).toContain("box-shadow: none;");
  });

  it("disables the sidebar width transition while resizing", () => {
    expect(ruleFor(".sidebar-shell.resizing")).toContain("transition: none;");
  });

  it("reserves chat space while the fixed video note drawer is open", () => {
    expect(stylesheet).toMatch(
      /\.workspace\.video-note-open \.panel-chat-embedded\s*\{[^}]*margin-left:\s*var\(--video-note-drawer-width,\s*720px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.workspace\.video-note-open \.sidebar-shell,[\s\S]*?\.workspace\.video-note-open \.resizer\s*\{[^}]*display:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 1024px\)\s*\{[\s\S]*?\.workspace\.video-note-open \.panel-chat-embedded\s*\{[^}]*margin-left:\s*0;/s,
    );
  });
});
