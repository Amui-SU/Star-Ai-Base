import { describe, expect, it } from "vitest";

import { LLM_PROVIDER_PRESETS, PROVIDER_PRESETS } from "@/lib/providers";

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
});
