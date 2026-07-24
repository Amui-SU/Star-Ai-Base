import { describe, expect, it } from "vitest";

import {
  formatApiAccountConfig,
  normalizeApiAccountConfig,
  parseApiAccountConfig,
  updateApiAccountConfig,
} from "@/lib/apiAccountConfig";

describe("API account advanced config", () => {
  it("normalizes v1 fields without mutating or losing unknown top-level data", () => {
    const source = {
      version: 1,
      model_mapping: { chat: "vendor-chat" },
      vendor_extension: { region: "cn", nested: [1, 2] },
    };
    const snapshot = structuredClone(source);

    expect(normalizeApiAccountConfig(source, "fallback")).toEqual({
      version: 1,
      model_mapping: { chat: "vendor-chat" },
      fallback_model: "fallback",
      user_agent: "",
      headers: {},
      body: {},
      vendor_extension: { region: "cn", nested: [1, 2] },
    });
    expect(source).toEqual(snapshot);
  });

  it("round trips form changes while preserving unknown fields", () => {
    const parsed = parseApiAccountConfig(
      '{"version":1,"vendor":{"keep":true},"headers":{"X-Route":"a"}}',
    );
    const updated = updateApiAccountConfig(parsed, {
      model_mapping: { primary: "gpt-real" },
      fallback_model: "gpt-fallback",
    });

    expect(JSON.parse(formatApiAccountConfig(updated))).toMatchObject({
      vendor: { keep: true },
      headers: { "X-Route": "a" },
      model_mapping: { primary: "gpt-real" },
      fallback_model: "gpt-fallback",
    });
  });

  it("reports JSON syntax positions and typed field paths", () => {
    expect(() => parseApiAccountConfig('{\n  "body": {\n}')).toThrow(
      /line 3, column 2/i,
    );
    expect(() =>
      normalizeApiAccountConfig({ headers: { Authorization: "secret" } }),
    ).toThrow(/headers\.Authorization/);
    expect(() =>
      normalizeApiAccountConfig({ body: { model: "override" } }),
    ).toThrow(/body\.model/);
  });

  it("requires an object and validates mapping/header/body types", () => {
    expect(() => parseApiAccountConfig("[]")).toThrow(/root/);
    expect(() =>
      normalizeApiAccountConfig({ model_mapping: { "": "model" } }),
    ).toThrow(/model_mapping/);
    expect(() => normalizeApiAccountConfig({ headers: [] })).toThrow(/headers/);
    expect(() => normalizeApiAccountConfig({ body: [] })).toThrow(/body/);
  });
});
