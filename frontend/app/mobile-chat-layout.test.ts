import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(
  resolve(process.cwd(), "app", "globals.css"),
  "utf8",
);

describe("mobile chat message layout", () => {
  it("uses the warm accent palette for light-theme user messages", () => {
    expect(stylesheet).toMatch(
      /html\.light\s*\{[^}]*--user-bubble-bg:\s*linear-gradient\(135deg,\s*#a85d12,\s*#8f4f12\);[^}]*--user-bubble-color:\s*#fffaf2;/s,
    );
  });

  it("allows the user menu to escape the expanded mobile topbar", () => {
    expect(stylesheet).toMatch(
      /\.app-shell\.sidebar-open \.workspace-topbar\s*\{[^}]*overflow:\s*visible;/s,
    );
    expect(stylesheet).toMatch(
      /\.app-shell\.sidebar-open \.workspace-topbar\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*80;/s,
    );
  });

  it("keeps edited user messages right-aligned and insets assistant replies", () => {
    expect(stylesheet).toMatch(
      /\.message\.user \.message-bubble\.editing\s*\{[^}]*align-self:\s*flex-end;[^}]*width:\s*min\(88%, 600px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.message\.assistant \.message-main\s*\{[^}]*padding-inline:\s*clamp\(12px, 4vw, 24px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.message\.assistant \.markdown\s*\{[^}]*text-align:\s*left;/s,
    );
  });

  it("hides the mobile chat scrollbar without disabling scrolling", () => {
    expect(stylesheet).toMatch(
      /\.panel-chat-embedded \.panel-body\s*\{[^}]*overflow-y:\s*auto;[^}]*scrollbar-width:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-chat-embedded \.panel-body::-webkit-scrollbar\s*\{[^}]*display:\s*none;/s,
    );
  });

  it("hides the provider config body scrollbar without disabling scrolling", () => {
    expect(stylesheet).toMatch(
      /\.provider-config-body\s*\{[^}]*overflow-y:\s*auto;[^}]*scrollbar-width:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.provider-config-body::-webkit-scrollbar\s*\{[^}]*display:\s*none;/s,
    );
  });

  it("keeps the mobile import modal above the workspace with screen insets", () => {
    expect(stylesheet).toMatch(
      /\.modal-backdrop:has\(>\s*\.import-modal\)\s*\{[^}]*z-index:\s*100;[^}]*align-items:\s*center;[^}]*padding:\s*16px;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-modal,\s*\.import-modal-step\s*\{[^}]*width:\s*min\(100%, calc\(100vw - 32px\)\);/s,
    );
  });
});
