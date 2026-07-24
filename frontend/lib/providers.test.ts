import { describe, expect, it } from "vitest";

import {
  LLM_PROVIDER_PRESETS,
  PROVIDER_PRESETS,
  providerLogoMap,
} from "@/lib/providers";

describe("provider presets", () => {
  it("keeps API account defaults and chat model menu order unchanged", () => {
    expect(PROVIDER_PRESETS.map((preset) => preset.provider)).toEqual([
      "deepseek",
      "dashscope",
      "openai",
      "agnes",
      "claude",
      "kimi",
      "siliconflow",
      "zhipu",
      "tavily",
    ]);
    expect(LLM_PROVIDER_PRESETS.map((preset) => preset.provider)).toEqual([
      "dashscope",
      "deepseek",
      "openai",
      "agnes",
      "claude",
      "kimi",
      "siliconflow",
      "zhipu",
    ]);
  });

  it("uses the official Agnes icon in provider menus", () => {
    expect(providerLogoMap.get("agnes")).toBe("/logos/agnes-icon.svg");
  });

  it("describes connection protocols and reduced search sections", () => {
    const claude = PROVIDER_PRESETS.find(
      ({ provider }) => provider === "claude",
    );
    const tavily = PROVIDER_PRESETS.find(
      ({ provider }) => provider === "tavily",
    );

    expect(claude).toMatchObject({
      protocol: "anthropic_messages",
      authScheme: "x_api_key",
      websiteUrl: "https://www.anthropic.com/",
    });
    expect(tavily).toMatchObject({
      protocol: null,
      authScheme: null,
      kind: "search",
      sections: ["identity", "connection"],
    });
  });
});
