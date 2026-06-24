import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(
  resolve(process.cwd(), "app", "globals.css"),
  "utf8",
);

describe("source ingestion status theme", () => {
  it("uses existing blue semantic badges for dark-theme ingested states", () => {
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\s*\{[^}]*padding:\s*3px 7px;[^}]*border:\s*1px solid transparent;[^}]*border-radius:\s*999px;/s,
    );
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\.ok\s*\{[^}]*background:\s*rgba\(95,\s*163,\s*255,\s*0\.15\);[^}]*border-color:\s*rgba\(95,\s*163,\s*255,\s*0\.3\);[^}]*color:\s*#a8ceff;/s,
    );
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\.partial\s*\{[^}]*background:\s*rgba\(217,\s*119,\s*87,\s*0\.14\);[^}]*border-color:\s*rgba\(240,\s*161,\s*131,\s*0\.34\);[^}]*color:\s*#f0a183;/s,
    );
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\.empty\s*\{[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.05\);[^}]*border-color:\s*rgba\(255,\s*255,\s*255,\s*0\.12\);[^}]*color:\s*#aaa69e;/s,
    );
  });

  it("keeps light-theme status badges subtle", () => {
    expect(stylesheet).toMatch(
      /html\.light \.folder-card \.status-pill\s*\{[^}]*background:\s*transparent;[^}]*border-color:\s*transparent;/s,
    );
  });
});

describe("chat web search light theme", () => {
  it("renders live web search progress as shimmering text without animating the container", () => {
    expect(stylesheet).toMatch(
      /\.web-search-live-status\s*\{[^}]*border:\s*0;[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*0\.68\);[^}]*background:\s*transparent;[^}]*font-weight:\s*500;/s,
    );
    expect(stylesheet).not.toMatch(/\.web-search-live-status::before\s*\{/);
    expect(stylesheet).toMatch(
      /\.web-search-live-text\s*\{[^}]*background:\s*linear-gradient\(\s*90deg,\s*rgba\(255,\s*255,\s*255,\s*0\.58\),\s*rgba\(255,\s*255,\s*255,\s*0\.98\),\s*rgba\(255,\s*255,\s*255,\s*0\.58\)\s*\);[^}]*background-size:\s*260% 100%;[^}]*animation:\s*webSearchTextShimmer 4\.8s linear infinite;[^}]*will-change:\s*background-position;/s,
    );
    expect(stylesheet).toMatch(
      /@keyframes webSearchTextShimmer\s*\{\s*0%\s*\{[^}]*background-position:\s*220% 50%;[^}]*\}\s*100%\s*\{[^}]*background-position:\s*-120% 50%;[^}]*\}\s*\}/s,
    );
    const shimmerKeyframes =
      stylesheet.match(
        /@keyframes webSearchTextShimmer\s*\{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    expect(shimmerKeyframes).not.toContain("56%");
    expect(stylesheet).toMatch(
      /\.web-search-live-dot\s*\{[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.78\);[^}]*box-shadow:\s*0 0 10px rgba\(255,\s*255,\s*255,\s*0\.2\);/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.web-search-live-status\s*\{[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*0\.68\);[^}]*background:\s*transparent;/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.web-search-live-dot\s*\{[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.78\);[^}]*box-shadow:\s*0 0 10px rgba\(255,\s*255,\s*255,\s*0\.2\);/s,
    );
  });

  it("uses the existing green treatment for web search controls and notices", () => {
    expect(stylesheet).toMatch(
      /html\.light \.scope-picker-trigger\.web-search-enabled:not\(\[aria-expanded="true"\]\),\s*html\.light \.scope-picker-trigger\.web-search-notice:not\(\[aria-expanded="true"\]\)\s*\{[^}]*background:\s*rgba\(47,\s*124,\s*120,\s*0\.15\);[^}]*border-color:\s*rgba\(47,\s*124,\s*120,\s*0\.35\);[^}]*color:\s*#1f7a75;/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.scope-picker-trigger\.web-search-notice:not\(\[aria-expanded="true"\]\)\s*\{[^}]*animation-name:\s*webSearchPulseLight;/s,
    );
    expect(stylesheet).toMatch(
      /@keyframes webSearchPulseLight\s*\{[\s\S]*box-shadow:\s*0 0 0 5px rgba\(47,\s*124,\s*120,\s*0\.16\);[\s\S]*\}/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.scope-web-search-btn\.active\s*\{[^}]*border-color:\s*rgba\(47,\s*124,\s*120,\s*0\.35\);[^}]*background:\s*rgba\(47,\s*124,\s*120,\s*0\.15\);[^}]*color:\s*#1f7a75;/s,
    );
    expect(stylesheet).toMatch(
      /html\.light \.web-search-status\.no_results\s*\{[^}]*border-color:\s*rgba\(47,\s*124,\s*120,\s*0\.3\);[^}]*background:\s*rgba\(47,\s*124,\s*120,\s*0\.1\);[^}]*color:\s*#1f7a75;/s,
    );
  });

  it("uses a green primary send button instead of the dark light-theme button", () => {
    expect(stylesheet).toMatch(
      /html\.light \.composer-send-button\.active,\s*html\.light \.composer-send-button\.generating,\s*html\.light \.mode-chip\.mode-chip-send\.active\s*\{[^}]*background:\s*#2f7c78;[^}]*color:\s*#fffaf2;/s,
    );
    expect(stylesheet).toMatch(
      /\.composer-send-button:disabled\s*\{[^}]*background:\s*rgba\(248,\s*246,\s*241,\s*0\.74\);[^}]*color:\s*rgba\(32,\s*32,\s*30,\s*0\.72\);[^}]*\}\s*html\.light \.mode-chip\.mode-chip-send\.active,\s*html\.light \.composer-send-button\.active,\s*html\.light \.composer-send-button\.generating\s*\{[^}]*background:\s*#2f7c78;[^}]*color:\s*#fffaf2;/s,
    );
  });
});
