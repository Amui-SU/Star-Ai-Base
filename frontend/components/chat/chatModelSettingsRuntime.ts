import {
  chatApi,
  type LLMApiSource,
  type LLMConfigResponse,
  type LLMHealthResponse,
  type LLMProvider,
} from "@/lib/api";
import type { ThinkingMode } from "@/lib/thinkingConfig";

export interface LoadedModelSettings {
  config: LLMConfigResponse;
  health: LLMHealthResponse;
}

export interface ProviderModelConfigPayload {
  provider: string;
  api_key?: string;
  base_url?: string;
  model?: string;
  thinking_mode: ThinkingMode;
  thinking_config?: Record<string, unknown>;
}

export interface SavedProviderModelConfig extends LoadedModelSettings {
  saved: Awaited<ReturnType<typeof chatApi.saveModelProviderConfig>>;
}

export class ModelSwitchError extends Error {
  health: LLMHealthResponse;

  constructor(message: string, health: LLMHealthResponse) {
    super(message);
    this.name = "ModelSwitchError";
    this.health = health;
  }
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export function buildModelSwitchFailureHealth(err: unknown): LLMHealthResponse {
  return {
    status: "down",
    message: errorMessage(err, "模型切换失败"),
    model: "unknown",
    provider: "unknown",
  };
}

export async function loadModelConfig(): Promise<LLMConfigResponse> {
  return chatApi.getModelConfig();
}

export async function checkModelHealth(): Promise<LLMHealthResponse> {
  return chatApi.health();
}

export async function loadModelSettings(): Promise<LoadedModelSettings> {
  const [config, health] = await Promise.all([
    loadModelConfig(),
    checkModelHealth(),
  ]);
  return { config, health };
}

export async function saveProviderModelConfig(
  payload: ProviderModelConfigPayload,
): Promise<SavedProviderModelConfig> {
  const saved = await chatApi.saveModelProviderConfig(payload);
  const loaded = await loadModelSettings();
  return { saved, ...loaded };
}

export async function switchModelProvider(
  provider: LLMProvider,
): Promise<LoadedModelSettings> {
  try {
    await chatApi.setModelProvider(provider);
    return await loadModelSettings();
  } catch (err) {
    const health = buildModelSwitchFailureHealth(err);
    throw new ModelSwitchError(health.message, health);
  }
}

export async function switchModelSource(
  apiSource: LLMApiSource,
): Promise<LoadedModelSettings> {
  const config = await chatApi.setModelSource(apiSource);
  const health = await checkModelHealth();
  return { config, health };
}
