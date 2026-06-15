import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(
  resolve(process.cwd(), "app", "globals.css"),
  "utf8",
);

describe("source ingestion status theme", () => {
  it("uses distinct semantic badges for dark-theme ingestion states", () => {
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\s*\{[^}]*padding:\s*3px 7px;[^}]*border:\s*1px solid transparent;[^}]*border-radius:\s*999px;/s,
    );
    expect(stylesheet).toMatch(
      /\.folder-card \.status-pill\.ok\s*\{[^}]*background:\s*rgba\(72,\s*187,\s*120,\s*0\.16\);[^}]*border-color:\s*rgba\(110,\s*231,\s*143,\s*0\.34\);[^}]*color:\s*#a7efb8;/s,
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
