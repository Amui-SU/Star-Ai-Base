import { describe, expect, it } from "vitest";

import {
  buildModelSourceOptions,
  buildProvidersForMenu,
  hasEnabledCurrentSource,
  resolveCurrentApiSource,
  shouldShowAiKeyHint,
} from "@/components/chat/chatModelSettingsState";
import type { LLMConfigResponse } from "@/lib/api";

describe("chatModelSettingsState", () => {
  it("treats missing and legacy API source as official", () => {
    expect(resolveCurrentApiSource(null)).toBe("official");
    expect(resolveCurrentApiSource({} as LLMConfigResponse)).toBe("official");
    expect(
      resolveCurrentApiSource({
        current_api_source: "personal",
      } as LLMConfigResponse),
    ).toBe("personal");
  });

  it("builds the official and personal source menu options", () => {
    const options = buildModelSourceOptions();
    expect(options.map((option) => option.value)).toEqual([
      "official",
      "personal",
    ]);
    expect(options.map((option) => option.label)).toEqual(["官方", "个人"]);
    expect(options.map((option) => option.enabled)).toEqual([true, true]);
  });

  it("keeps the limited official channel selectable before a provider is configured", () => {
    const [official] = buildModelSourceOptions();

    expect(official).toMatchObject({
      value: "official",
      hint: "限制开放",
      enabled: true,
    });
  });

  it("detects whether the loaded provider set can serve the current source", () => {
    expect(
      hasEnabledCurrentSource([
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: false,
          model: "deepseek-chat",
          thinking_config: {},
          thinking_template: {},
        },
      ]),
    ).toBe(false);
    expect(
      hasEnabledCurrentSource([
        {
          provider: "deepseek",
          label: "DeepSeek",
          enabled: true,
          model: "deepseek-chat",
          thinking_config: {},
          thinking_template: {},
        },
      ]),
    ).toBe(true);
  });

  it("shows the AI key hint only after a personal-source config loads without usable providers", () => {
    expect(shouldShowAiKeyHint(null, "personal", false)).toBe(false);
    expect(
      shouldShowAiKeyHint(
        { current_api_source: "official" } as LLMConfigResponse,
        "official",
        false,
      ),
    ).toBe(false);
    expect(
      shouldShowAiKeyHint(
        { current_api_source: "personal" } as LLMConfigResponse,
        "personal",
        true,
      ),
    ).toBe(false);
    expect(
      shouldShowAiKeyHint(
        { current_api_source: "personal" } as LLMConfigResponse,
        "personal",
        false,
      ),
    ).toBe(true);
  });

  it("overlays remote provider details onto built-in presets and appends unknown providers", () => {
    const providers = buildProvidersForMenu([
      {
        provider: "deepseek",
        label: "DeepSeek Remote",
        enabled: true,
        official_enabled: true,
        personal_enabled: true,
        model: "deepseek-v4-pro",
        base_url: "https://example.test",
        thinking_config: { enabled: true },
        thinking_template: { type: "standard" },
      },
      {
        provider: "custom-model",
        label: "Custom Model",
        enabled: true,
        model: "custom-v1",
        thinking_config: {},
        thinking_template: {},
      },
    ]);

    expect(providers[0].provider).toBe("dashscope");
    const deepseek = providers.find(
      (provider) => provider.provider === "deepseek",
    );
    expect(deepseek).toMatchObject({
      label: "DeepSeek Remote",
      enabled: true,
      official_enabled: true,
      personal_enabled: true,
      model: "deepseek-v4-pro",
      base_url: "https://example.test",
    });
    expect(providers.at(-1)).toMatchObject({
      provider: "custom-model",
      label: "Custom Model",
      enabled: true,
      model: "custom-v1",
    });
  });
});
