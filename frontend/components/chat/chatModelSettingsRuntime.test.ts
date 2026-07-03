import { describe, expect, it, vi } from "vitest";

import {
  loadModelSettings,
  saveProviderModelConfig,
  switchModelProvider,
  switchModelSource,
} from "@/components/chat/chatModelSettingsRuntime";
import { chatApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
      health: vi.fn(),
      saveModelProviderConfig: vi.fn(),
      setModelProvider: vi.fn(),
      setModelSource: vi.fn(),
    },
  };
});

describe("chatModelSettingsRuntime", () => {
  const config = {
    current_provider: "deepseek",
    current_api_source: "official" as const,
    providers: [],
  };
  const health = {
    status: "up",
    message: "ok",
    latency_ms: 42,
    model: "deepseek-chat",
    provider: "deepseek",
  };

  it("loads model config and health in one runtime call", async () => {
    vi.mocked(chatApi.getModelConfig).mockResolvedValue(config);
    vi.mocked(chatApi.health).mockResolvedValue(health);

    await expect(loadModelSettings()).resolves.toEqual({ config, health });
  });

  it("saves provider config then refreshes config and health", async () => {
    vi.mocked(chatApi.saveModelProviderConfig).mockResolvedValue({
      ok: true,
      current_provider: "deepseek",
      model: "deepseek-chat",
      provider_label: "DeepSeek",
      thinking_config: {},
      thinking_template: {},
      verified: true,
      latency_ms: 88,
    });
    vi.mocked(chatApi.getModelConfig).mockResolvedValue(config);
    vi.mocked(chatApi.health).mockResolvedValue(health);

    await expect(
      saveProviderModelConfig({
        provider: "deepseek",
        api_key: "sk-test",
        thinking_mode: "off",
      }),
    ).resolves.toEqual({
      saved: expect.objectContaining({ latency_ms: 88 }),
      config,
      health,
    });
  });

  it("switches provider then refreshes config and health", async () => {
    vi.mocked(chatApi.setModelProvider).mockResolvedValue({
      ok: true,
      current_provider: "deepseek",
      model: "deepseek-chat",
    });
    vi.mocked(chatApi.getModelConfig).mockResolvedValue(config);
    vi.mocked(chatApi.health).mockResolvedValue(health);

    await expect(switchModelProvider("deepseek")).resolves.toEqual({
      config,
      health,
    });
  });

  it("switches source then refreshes health from the saved config response", async () => {
    vi.mocked(chatApi.setModelSource).mockResolvedValue(config);
    vi.mocked(chatApi.health).mockResolvedValue(health);

    await expect(switchModelSource("official")).resolves.toEqual({
      config,
      health,
    });
  });

  it("builds the existing down health fallback from provider switch failures", async () => {
    vi.mocked(chatApi.setModelProvider).mockRejectedValue(
      new Error("provider failed"),
    );

    await expect(switchModelProvider("deepseek")).rejects.toMatchObject({
      health: {
        status: "down",
        message: "provider failed",
        model: "unknown",
        provider: "unknown",
      },
    });
  });
});
