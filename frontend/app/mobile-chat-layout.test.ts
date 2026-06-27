import { describe, expect, it } from "vitest";

import { readStylesheetWithLocalImports } from "./testStyles";

const stylesheet = readStylesheetWithLocalImports();

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
      /\.app-shell\.sidebar-open \.workspace-topbar\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*140;/s,
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
      /\.modal-backdrop:has\(>\s*\.import-modal\)\s*\{[^}]*z-index:\s*230;[^}]*align-items:\s*center;[^}]*padding:\s*16px;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-modal,\s*\.import-modal-step\s*\{[^}]*width:\s*min\(100%, calc\(100vw - 32px\)\);/s,
    );
  });

  it("adapts the local video import card for narrow mobile screens", () => {
    expect(stylesheet).toMatch(/\.import-step-body\s*\{[^}]*gap:\s*12px;/s);
    expect(stylesheet).toMatch(
      /\.import-local-video-input\s*\{[^}]*width:\s*100%;[^}]*max-width:\s*100%;[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-local-video-input::file-selector-button\s*\{[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*margin:\s*0 0 8px;[^}]*min-height:\s*32px;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-local-video-card\s*\{[^}]*min-width:\s*0;[^}]*border-radius:\s*14px;[^}]*padding:\s*12px;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-local-video-title\s*\{[^}]*white-space:\s*normal;[^}]*overflow-wrap:\s*anywhere;/s,
    );
    expect(stylesheet).toMatch(
      /\.import-actions\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);/s,
    );
  });

  it("prevents the LAN QR card from showing its own right-side scrollbar", () => {
    expect(stylesheet).toMatch(
      /\.local-connection-qr-card\s*\{[^}]*overflow:\s*hidden;[^}]*scrollbar-width:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.local-connection-qr-card::-webkit-scrollbar\s*\{[^}]*display:\s*none;/s,
    );
  });

  it("keeps mobile connection settings readable and above admin overlays", () => {
    expect(stylesheet).toMatch(
      /\.modal-backdrop\.local-connection-modal-backdrop\s*\{[^}]*z-index:\s*230;/s,
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 1024px\)\s*\{[\s\S]*\.local-connection-modal-backdrop\s*\{[^}]*align-items:\s*flex-start;[^}]*overflow-y:\s*auto;[^}]*padding:\s*max\(16px, calc\(env\(safe-area-inset-top\) \+ 12px\)\)\s+14px\s+max\(22px, calc\(env\(safe-area-inset-bottom\) \+ 16px\)\);/s,
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 1024px\)\s*\{[\s\S]*\.local-connection-modal\s*\{[^}]*width:\s*min\(100%, 420px\);[^}]*max-height:\s*none;[^}]*margin:\s*0 auto;/s,
    );
    expect(stylesheet).toMatch(
      /\.local-connection-trigger\s*\{[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;/s,
    );
    expect(stylesheet).toMatch(
      /\.local-connection-trigger-label\s*\{[^}]*display:\s*inline;[^}]*white-space:\s*nowrap;/s,
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 640px\)\s*\{[\s\S]*\.auth-page \.local-connection-trigger\s*\{[^}]*min-width:\s*74px;[^}]*padding-inline:\s*10px;[^}]*color:\s*#faf9f5;/s,
    );
  });

  it("uses an opaque knowledge selector menu on mobile", () => {
    expect(stylesheet).toMatch(
      /@media \(max-width: 1024px\)\s*\{[\s\S]*\.knowledge-select-popover\s*\{[^}]*background:\s*#262624;[^}]*backdrop-filter:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 1024px\)\s*\{[\s\S]*html\.light \.knowledge-select-popover\s*\{[^}]*background:\s*#f8efe2;/s,
    );
  });

  it("rebalances the mobile empty state with the title higher and composer lower", () => {
    expect(stylesheet).toMatch(
      /\.panel-chat-embedded \.panel-body:has\(\.empty-state\)\s*\{[^}]*padding-top:\s*clamp\(30px, 8dvh, 88px\);/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-chat-embedded \.empty-state,\s*html\.light \.panel-chat-embedded \.empty-state\s*\{[^}]*transform:\s*translateY\(clamp\(-82px, -10dvh, -46px\)\);/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-chat-embedded \.panel-footer:has\(\.composer-shell\)\s*\{[^}]*padding-bottom:\s*max\(22px, env\(safe-area-inset-bottom\)\);/s,
    );
  });

  it("uses a collapsed three-icon toolstrip and keeps the expanded round collapse button", () => {
    expect(stylesheet).toMatch(
      /\.workspace-corner-tools\s*\{[^}]*position:\s*absolute;[^}]*top:\s*11px;[^}]*left:\s*16px;/s,
    );
    expect(stylesheet).toMatch(
      /\.workspace-corner-tools\s*\{[^}]*border-radius:\s*999px;[^}]*background:\s*var\(--paper-2\);[^}]*padding:\s*2px;[^}]*box-shadow:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.workspace-corner-tool\s*\{[^}]*width:\s*26px;[^}]*height:\s*26px;/s,
    );
    expect(stylesheet).toMatch(
      /\.workspace-sidebar-toggle\s*\{[^}]*top:\s*11px;[^}]*left:\s*16px !important;[^}]*width:\s*32px;[^}]*height:\s*32px;[^}]*border-radius:\s*999px;[^}]*box-shadow:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.workspace-sidebar-toggle \.sidebar-toggle-icon\s*\{[^}]*display:\s*block;/s,
    );
    expect(stylesheet).toMatch(
      /\.chat-context-row\s*\{[^}]*justify-content:\s*flex-end;/s,
    );
    expect(stylesheet).toMatch(/\.chat-kb-meta\s*\{[^}]*display:\s*none;/s);
    expect(stylesheet).toMatch(
      /\.app-shell\.sidebar-open \.knowledge-panel-head\s*\{[^}]*padding-left:\s*46px;/s,
    );
    expect(stylesheet).toMatch(
      /\.app-shell\.sidebar-open \.workspace\s*\{[^}]*height:\s*auto;[^}]*min-height:\s*0;/s,
    );
    expect(stylesheet).toMatch(
      /\.app-shell\.sidebar-open \.sidebar-shell,\s*\.app-shell\.sidebar-open \.panel-sources\s*\{[^}]*height:\s*100%;[^}]*max-height:\s*100%;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-sources\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*min-height:\s*0;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-sources > \.sources-panel-empty,\s*\.panel-sources > \.panel-inner:not\(\.sources-panel-empty\)\s*\{[^}]*flex:\s*1 1 auto;[^}]*min-height:\s*0;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-sources > \.sources-panel-empty \.panel-body,\s*\.panel-sources > \.panel-inner:not\(\.sources-panel-empty\) \.panel-body\s*\{[^}]*flex:\s*1 1 auto;[^}]*min-height:\s*0;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-sources \.panel-footer\s*\{[^}]*padding:\s*10px 16px max\(20px, calc\(env\(safe-area-inset-bottom\) \+ 8px\)\);[^}]*flex-shrink:\s*0;/s,
    );
    expect(stylesheet).toMatch(
      /\.sources-panel-empty \.sources-scroll\s*\{[^}]*min-height:\s*0;[^}]*justify-content:\s*flex-start;/s,
    );
    expect(stylesheet).toMatch(
      /\.sources-panel-empty \.sources-empty-state\s*\{[^}]*flex:\s*0 0 auto;[^}]*min-height:\s*auto;[^}]*align-items:\s*flex-start;/s,
    );
    expect(stylesheet).toMatch(
      /\.sources-panel-empty \.sources-empty-card\s*\{[^}]*align-self:\s*center;[^}]*min-height:\s*auto;/s,
    );
    expect(stylesheet).toMatch(
      /\.user-menu-profile-avatar\s*\{[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;/s,
    );
    expect(stylesheet).toMatch(
      /\.user-menu-profile-avatar \.user-menu-avatar\s*\{[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*height:\s*100%;/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-shell\s*\{[^}]*width:\s*100vw !important;[^}]*max-width:\s*100vw;/s,
    );
    expect(stylesheet).toMatch(
      /\.panel-sources\s*\{[^}]*width:\s*100vw !important;[^}]*max-width:\s*100vw;/s,
    );
    expect(stylesheet).toMatch(
      /\.composer-disclaimer\s*\{[^}]*display:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.composer-mode-row\s*\{[^}]*right:\s*8px;[^}]*left:\s*auto;[^}]*top:\s*calc\(50% - 19px\);[^}]*transform:\s*none;[^}]*justify-content:\s*flex-end;/s,
    );
    expect(stylesheet).toMatch(/\.scope-picker\s*\{[^}]*position:\s*static;/s);
    expect(stylesheet).toMatch(
      /\.scope-picker-trigger\s*\{[^}]*position:\s*static;[^}]*transform:\s*none;/s,
    );
    expect(stylesheet).toMatch(
      /\.scope-picker-popover\s*\{[^}]*position:\s*fixed;[^}]*left:\s*50%;[^}]*right:\s*auto;[^}]*bottom:\s*max\(96px, calc\(env\(safe-area-inset-bottom\) \+ 96px\)\);[^}]*transform:\s*translateX\(-50%\);/s,
    );
    expect(stylesheet).toMatch(
      /\.composer-send-button\s*\{[^}]*position:\s*static;/s,
    );
  });

  it("keeps the chat history sidebar header compact and uses existing control styling", () => {
    expect(stylesheet).toMatch(
      /\.chat-history-sidebar-panel\s*\{[^}]*gap:\s*8px;[^}]*padding:\s*8px 12px 14px;/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-history-topbar\s*\{[^}]*align-items:\s*center;[^}]*justify-content:\s*space-between;[^}]*min-height:\s*34px;/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-history-actions\s*\{[^}]*display:\s*inline-flex;[^}]*gap:\s*8px;[^}]*padding-right:\s*4px;/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-history-new-chat\s*\{[^}]*width:\s*min\(100%, 220px\);[^}]*min-height:\s*32px;[^}]*background:\s*var\(--paper-2\);/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.sidebar-history-new-chat\s*\{[^}]*border-color:\s*var\(--border-strong\);[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.55\);[^}]*box-shadow:\s*none;[^}]*color:\s*var\(--ink-soft\);/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.sidebar-history-new-chat:hover\s*\{[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.78\);/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-history-collapse\s*\{[^}]*width:\s*26px;[^}]*height:\s*26px;[^}]*border:\s*0;[^}]*background:\s*transparent;/s,
    );
    expect(stylesheet).toMatch(
      /\.sidebar-history-list\s*\{[^}]*padding:\s*8px 6px 4px 4px;/s,
    );
    expect(stylesheet).toMatch(
      /\.chat-history-sidebar-panel \.sidebar-tool-empty\s*\{[^}]*margin-top:\s*18px;/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.chat-history-sidebar-panel \.sidebar-tool-empty\s*\{[^}]*border-color:\s*rgba\(205,\s*187,\s*159,\s*0\.72\);[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.16\);[^}]*box-shadow:\s*none;/s,
    );
  });
});
