import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { readStylesheetWithLocalImports } from "./testStyles";

const stylesheet = readStylesheetWithLocalImports();
const modelStatusSource = readFileSync(
  resolve(process.cwd(), "components/chat/ChatModelStatus.tsx"),
  "utf8",
);

describe("official model API configuration layout", () => {
  it("uses a viewport-safe desktop modal with one scrolling editor body", () => {
    expect(stylesheet).toMatch(
      /\.thinking-provider-modal\s*\{[^}]*width:\s*min\(840px,\s*calc\(100vw - 32px\)\);[^}]*overflow:\s*hidden;/s,
    );
    expect(stylesheet).toMatch(
      /\.thinking-provider-modal\s+\.api-credential-editor-body\s*\{[^}]*overflow-y:\s*auto;/s,
    );
  });

  it("keeps the mobile modal in a single column", () => {
    expect(stylesheet).toMatch(
      /@media \(max-width:\s*640px\)\s*\{[\s\S]*?\.thinking-provider-modal\s*\{[^}]*width:\s*min\(100%,\s*calc\(100vw - 16px\)\);[\s\S]*?\.provider-config-fields\s*\{[^}]*grid-template-columns:\s*1fr;/s,
    );
  });
});

describe("personal API account layout", () => {
  it("uses a two-column account grid and two-column basic field grid", () => {
    expect(stylesheet).toMatch(
      /\.api-accounts-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/s,
    );
    expect(stylesheet).toMatch(
      /\.api-account-basic-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/s,
    );
  });

  it("collapses account and basic grids to one column on mobile", () => {
    expect(stylesheet).toMatch(
      /@media \(max-width:\s*640px\)\s*\{[\s\S]*?\.api-accounts-grid,[\s\S]*?\.api-account-basic-grid\s*\{[^}]*grid-template-columns:\s*1fr;/s,
    );
  });

  it("removes the legacy split list and form layout", () => {
    expect(stylesheet).not.toMatch(/\.api-accounts-layout\s*\{/);
  });
});

describe("model source switch", () => {
  it("renders two stable equal-width segments", () => {
    expect(stylesheet).toMatch(
      /\.model-source-switch\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/s,
    );
    expect(stylesheet).toMatch(
      /\.model-source-option\s*\{[^}]*min-height:\s*48px;[^}]*border-radius:\s*8px;/s,
    );
  });

  it("uses the warm accent surface without wrapping its labels", () => {
    expect(stylesheet).toMatch(
      /\.model-source-option\.active\s*\{[^}]*border-color:\s*rgba\(217,\s*119,\s*87,[^)]+\);[^}]*background:\s*rgba\(217,\s*119,\s*87,[^)]+\);[^}]*color:\s*var\(--accent-strong\);/s,
    );
    expect(stylesheet).toMatch(
      /\.model-source-option\s+(?:span|small),\s*\n?\.model-source-option\s+(?:span|small)\s*\{[^}]*white-space:\s*nowrap;/s,
    );
  });

  it("preserves provider rendering and switch/configure handlers", () => {
    expect(modelStatusSource).toContain("providers.map((provider)");
    expect(modelStatusSource).toContain("onSwitchProvider(provider.provider)");
    expect(modelStatusSource).toContain("onConfigureProvider(provider)");
  });
});
