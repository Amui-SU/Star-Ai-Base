import type { ModelConfigProvider } from "@/components/chat/types";
import type {
  LLMApiSource,
  LLMConfigResponse,
  LLMProviderInfo,
} from "@/lib/api";
import { LLM_PROVIDER_PRESETS } from "@/lib/providers";

export const EMPTY_PROVIDERS: LLMProviderInfo[] = [];

export interface ModelSourceOption {
  value: LLMApiSource;
  label: string;
  hint: string;
  enabled: boolean;
}

export interface ModelMenuProvider extends ModelConfigProvider {
  official_enabled?: boolean;
  personal_enabled?: boolean;
}

export interface ModelSourceAvailability {
  official: boolean;
  personal: boolean;
}

export function resolveCurrentApiSource(
  llmConfig: Pick<LLMConfigResponse, "current_api_source"> | null | undefined,
): LLMApiSource {
  return llmConfig?.current_api_source === "personal" ? "personal" : "official";
}

export function resolveSourceAvailability(
  remoteProviders: readonly LLMProviderInfo[],
): ModelSourceAvailability {
  return {
    official: remoteProviders.some(
      (provider) => provider.official_enabled ?? provider.enabled,
    ),
    personal: remoteProviders.some(
      (provider) => provider.personal_enabled ?? provider.enabled,
    ),
  };
}

export function hasEnabledCurrentSource(
  remoteProviders: readonly LLMProviderInfo[],
): boolean {
  return remoteProviders.some((provider) => provider.enabled);
}

export function shouldShowAiKeyHint(
  llmConfig: LLMConfigResponse | null,
  currentApiSource: LLMApiSource,
  currentSourceHasEnabledProvider: boolean,
): boolean {
  return (
    Boolean(llmConfig) &&
    currentApiSource === "personal" &&
    !currentSourceHasEnabledProvider
  );
}

export function buildModelSourceOptions(
  sourceAvailability: ModelSourceAvailability,
): ModelSourceOption[] {
  return [
    {
      value: "official",
      label: "官方",
      hint: "付费通道",
      enabled: sourceAvailability.official,
    },
    {
      value: "personal",
      label: "个人",
      hint: "自带 Key",
      enabled: true,
    },
  ];
}

export function buildProvidersForMenu(
  remoteProviders: readonly LLMProviderInfo[],
): ModelMenuProvider[] {
  const remoteProviderMap = new Map(
    remoteProviders.map((provider) => [provider.provider, provider]),
  );

  return [
    ...LLM_PROVIDER_PRESETS.map((base) => {
      const remote = remoteProviderMap.get(base.provider);
      return {
        provider: base.provider,
        label: remote?.label ?? base.label,
        enabled: remote?.enabled ?? false,
        official_enabled: remote?.official_enabled ?? false,
        personal_enabled: remote?.personal_enabled ?? false,
        model: remote?.model ?? base.model,
        base_url: remote?.base_url,
        thinking_config: remote?.thinking_config ?? {},
        thinking_template: remote?.thinking_template ?? {},
      };
    }),
    ...remoteProviders.filter(
      (provider) =>
        !LLM_PROVIDER_PRESETS.some(
          (base) => base.provider === provider.provider,
        ),
    ),
  ];
}
