"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { ModelConfigProvider } from "@/components/chat/types";
import {
  chatApi,
  type LLMApiSource,
  type LLMConfigResponse,
  type LLMHealthResponse,
  type LLMProvider,
  type LLMProviderInfo,
} from "@/lib/api";
import { LLM_PROVIDER_PRESETS } from "@/lib/providers";
import {
  formatThinkingConfig,
  inferThinkingMode,
  parseThinkingConfig,
  type ThinkingMode,
} from "@/lib/thinkingConfig";

const EMPTY_PROVIDERS: LLMProviderInfo[] = [];

interface UseChatModelSettingsOptions {
  apiAccountsKey: number;
  isAdmin: boolean;
  onNotice: (message: string, timeoutMs?: number) => void;
}

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

export function useChatModelSettings({
  apiAccountsKey,
  isAdmin,
  onNotice,
}: UseChatModelSettingsOptions) {
  const [llmHealth, setLlmHealth] = useState<LLMHealthResponse | null>(null);
  const [llmChecking, setLlmChecking] = useState(false);
  const [llmConfig, setLlmConfig] = useState<LLMConfigResponse | null>(null);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [configProvider, setConfigProvider] =
    useState<ModelConfigProvider | null>(null);
  const [configApiKey, setConfigApiKey] = useState("");
  const [configBaseUrl, setConfigBaseUrl] = useState("");
  const [configModel, setConfigModel] = useState("");
  const [configThinkingMode, setConfigThinkingMode] =
    useState<ThinkingMode>("off");
  const [configThinkingJson, setConfigThinkingJson] = useState("{}");
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState("");

  const closeProviderConfig = useCallback(
    (force = false) => {
      if (configSaving && !force) return;
      setConfigProvider(null);
      setConfigApiKey("");
      setConfigBaseUrl("");
      setConfigModel("");
      setConfigThinkingMode("off");
      setConfigThinkingJson("{}");
      setConfigError("");
    },
    [configSaving],
  );

  const openProviderConfig = useCallback(
    (provider: ModelConfigProvider) => {
      if (!isAdmin) {
        onNotice("需要管理员配置模型");
        return;
      }
      setConfigProvider(provider);
      setConfigApiKey("");
      setConfigBaseUrl(provider.base_url || "");
      setConfigModel(provider.model || "");
      const thinkingConfig = provider.thinking_config || {};
      const thinkingTemplate = provider.thinking_template || {};
      const mode = inferThinkingMode(thinkingConfig, thinkingTemplate);
      setConfigThinkingMode(mode);
      setConfigThinkingJson(
        formatThinkingConfig(
          mode === "standard" ? thinkingTemplate : thinkingConfig,
        ),
      );
      setConfigError("");
      setModelMenuOpen(false);
    },
    [isAdmin, onNotice],
  );

  const handleSaveProviderConfig = useCallback(async () => {
    if (!configProvider || configSaving) return;
    if (!configProvider.enabled && !configApiKey.trim()) {
      setConfigError("请填写 API Key");
      return;
    }
    let thinkingConfig: Record<string, unknown> | undefined;
    if (configThinkingMode === "custom") {
      try {
        thinkingConfig = parseThinkingConfig(configThinkingJson);
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : "思考配置无效");
        return;
      }
    }
    setConfigSaving(true);
    setConfigError("");
    try {
      const saved = await chatApi.saveModelProviderConfig({
        provider: configProvider.provider,
        api_key: configApiKey.trim() || undefined,
        base_url: configBaseUrl.trim() || undefined,
        model: configModel.trim() || undefined,
        thinking_mode: configThinkingMode,
        thinking_config: thinkingConfig,
      });
      const [cfg, health] = await Promise.all([
        chatApi.getModelConfig(),
        chatApi.health(),
      ]);
      setLlmConfig(cfg);
      setLlmHealth(health);
      onNotice(`模型与思考配置验证成功 · ${saved.latency_ms}ms`, 2600);
      closeProviderConfig(true);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setConfigSaving(false);
    }
  }, [
    closeProviderConfig,
    configApiKey,
    configBaseUrl,
    configModel,
    configProvider,
    configSaving,
    configThinkingJson,
    configThinkingMode,
    onNotice,
  ]);

  useEffect(() => {
    let cancelled = false;
    const loadConfig = async () => {
      try {
        const cfg = await chatApi.getModelConfig();
        if (!cancelled) setLlmConfig(cfg);
      } catch {
        // 忽略配置加载失败，不影响聊天主流程
      }
    };
    const check = async () => {
      setLlmChecking(true);
      try {
        const res = await chatApi.health();
        if (!cancelled) setLlmHealth(res);
      } catch {
        if (!cancelled) {
          setLlmHealth({
            status: "down",
            message: "健康检查失败",
            model: "unknown",
            provider: "unknown",
          });
        }
      } finally {
        if (!cancelled) setLlmChecking(false);
      }
    };

    loadConfig();
    check();
    const timer = window.setInterval(check, 45000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [apiAccountsKey]);

  const handleSwitchProvider = useCallback(
    async (provider: LLMProvider) => {
      if (llmSwitching) return;
      setLlmSwitching(true);
      try {
        await chatApi.setModelProvider(provider);
        const [cfg, health] = await Promise.all([
          chatApi.getModelConfig(),
          chatApi.health(),
        ]);
        setLlmConfig(cfg);
        setLlmHealth(health);
      } catch (err) {
        setLlmHealth({
          status: "down",
          message: err instanceof Error ? err.message : "模型切换失败",
          model: "unknown",
          provider: "unknown",
        });
      } finally {
        setLlmSwitching(false);
      }
    },
    [llmSwitching],
  );

  const handleSwitchModelSource = useCallback(
    async (apiSource: LLMApiSource) => {
      if (llmSwitching || llmConfig?.current_api_source === apiSource) return;
      setLlmSwitching(true);
      try {
        const cfg = await chatApi.setModelSource(apiSource);
        const health = await chatApi.health();
        setLlmConfig(cfg);
        setLlmHealth(health);
      } catch (err) {
        onNotice(err instanceof Error ? err.message : "模型来源切换失败");
      } finally {
        setLlmSwitching(false);
      }
    },
    [llmConfig?.current_api_source, llmSwitching, onNotice],
  );

  const remoteProviders = llmConfig?.providers ?? EMPTY_PROVIDERS;
  const currentApiSource: LLMApiSource =
    llmConfig?.current_api_source === "personal" ? "personal" : "official";

  const sourceAvailability = useMemo(
    () => ({
      official: remoteProviders.some(
        (provider) => provider.official_enabled ?? provider.enabled,
      ),
      personal: remoteProviders.some(
        (provider) => provider.personal_enabled ?? provider.enabled,
      ),
    }),
    [remoteProviders],
  );

  const hasEnabledCurrentSource = useMemo(
    () => remoteProviders.some((provider) => provider.enabled),
    [remoteProviders],
  );

  const shouldShowAiKeyHint =
    Boolean(llmConfig) &&
    currentApiSource === "personal" &&
    !hasEnabledCurrentSource;

  const remoteProviderMap = useMemo(
    () =>
      new Map(remoteProviders.map((provider) => [provider.provider, provider])),
    [remoteProviders],
  );

  const sourceOptions: ModelSourceOption[] = useMemo(
    () => [
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
    ],
    [sourceAvailability.official],
  );

  const providersForMenu: ModelMenuProvider[] = useMemo(
    () => [
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
    ],
    [remoteProviderMap, remoteProviders],
  );

  const currentProvider =
    llmConfig?.current_provider ?? providersForMenu[0]?.provider;
  const activeProvider = providersForMenu.find(
    (provider) => provider.provider === currentProvider,
  );
  const modelReady = llmHealth?.status === "ok" || llmHealth?.status === "up";
  const modelStatusText = llmChecking
    ? "检查中"
    : modelReady
      ? "模型就绪"
      : "模型异常";
  const modelLatencyText =
    !llmChecking && llmHealth?.latency_ms != null
      ? `${llmHealth.latency_ms}ms`
      : "-- ms";
  const modelStatusTitle = activeProvider
    ? `${modelStatusText} · ${modelLatencyText} · ${activeProvider.label} · ${activeProvider.model}`
    : `${modelStatusText} · ${modelLatencyText}`;

  return {
    activeProvider,
    closeProviderConfig,
    configApiKey,
    configBaseUrl,
    configError,
    configModel,
    configProvider,
    configSaving,
    configThinkingJson,
    configThinkingMode,
    currentApiSource,
    currentProvider,
    handleSaveProviderConfig,
    handleSwitchModelSource,
    handleSwitchProvider,
    llmChecking,
    llmConfig,
    llmSwitching,
    modelLatencyText,
    modelMenuOpen,
    modelReady,
    modelStatusTitle,
    openProviderConfig,
    providersForMenu,
    setConfigApiKey,
    setConfigBaseUrl,
    setConfigError,
    setConfigModel,
    setConfigThinkingJson,
    setConfigThinkingMode,
    setModelMenuOpen,
    shouldShowAiKeyHint,
    sourceOptions,
  };
}
