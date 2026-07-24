"use client";

import { useCallback, useEffect, useState } from "react";
import {
  apiAccountApi,
  type ApiAccount,
  type ApiAccountDraftValidationResponse,
} from "@/lib/api";
import {
  formatApiAccountConfig,
  normalizeApiAccountConfig,
  parseApiAccountConfig,
  stableApiAccountConfig,
  updateApiAccountConfig,
  type ApiAccountConfigError,
} from "@/lib/apiAccountConfig";
import { PROVIDER_PRESETS, providerPresetMap } from "@/lib/providers";
import { inferThinkingMode, parseThinkingConfig } from "@/lib/thinkingConfig";
import type {
  ApiAccountSection,
  ApiAccountWorkspaceDraft,
  ThinkingTemplates,
} from "./types";

const firstPreset = PROVIDER_PRESETS[0];

function initialDraft(
  account: ApiAccount | null,
  templates: ThinkingTemplates,
): ApiAccountWorkspaceDraft {
  const preset =
    providerPresetMap.get(account?.provider ?? firstPreset.provider) ??
    firstPreset;
  const advancedConfig = normalizeApiAccountConfig(
    account?.advanced_config ?? {},
    account?.model ?? preset.model,
  );
  const thinking = account?.thinking_config ?? {};
  return {
    accountId: account?.id ?? null,
    provider: preset.provider,
    displayName: account?.display_name ?? "",
    notes: account?.notes ?? "",
    websiteUrl: account?.website_url ?? preset.websiteUrl,
    apiKey: "",
    baseUrl: account?.base_url ?? preset.baseUrl,
    model: account?.model ?? preset.model,
    protocol: account?.protocol ?? preset.protocol,
    authScheme: account?.auth_scheme ?? preset.authScheme,
    enabled: account?.enabled ?? true,
    isDefault: account?.is_default ?? false,
    thinkingMode: inferThinkingMode(thinking, templates[preset.provider] ?? {}),
    thinkingJson: JSON.stringify(thinking, null, 2),
    advancedConfig,
    modelMappingRows: Object.entries(advancedConfig.model_mapping).map(
      ([alias, model], index) => ({ id: `model-${index}`, alias, model }),
    ),
    headerRows: Object.entries(advancedConfig.headers).map(
      ([name, value], index) => ({ id: `header-${index}`, name, value }),
    ),
    bodyRaw: JSON.stringify(advancedConfig.body, null, 2),
  };
}

function thinkingConfig(
  draft: ApiAccountWorkspaceDraft,
  templates: ThinkingTemplates,
) {
  if (draft.thinkingMode === "off") return {};
  if (draft.thinkingMode === "standard") return templates[draft.provider] ?? {};
  return parseThinkingConfig(draft.thinkingJson);
}

function payload(
  draft: ApiAccountWorkspaceDraft,
  templates: ThinkingTemplates,
) {
  const preset = providerPresetMap.get(draft.provider) ?? firstPreset;
  return {
    provider: draft.provider,
    display_name: draft.displayName.trim() || preset.label,
    base_url: draft.baseUrl.trim(),
    model: draft.model.trim(),
    protocol: draft.protocol,
    auth_scheme: draft.authScheme,
    website_url: draft.websiteUrl.trim(),
    notes: draft.notes.trim(),
    advanced_config: normalizeApiAccountConfig({
      ...draft.advancedConfig,
      model_mapping: Object.fromEntries(
        draft.modelMappingRows.map((row) => [row.alias, row.model]),
      ),
      headers: Object.fromEntries(
        draft.headerRows.map((row) => [row.name, row.value]),
      ),
      body: JSON.parse(draft.bodyRaw),
    }),
    thinking_config:
      preset.kind === "search" ? {} : thinkingConfig(draft, templates),
    enabled: draft.enabled,
    is_default: draft.isDefault,
  };
}

interface Params {
  account: ApiAccount | null;
  templates: ThinkingTemplates;
  onBack: () => void;
  onClose: () => void;
  onSaved: () => void;
}

export function useApiAccountWorkspace({
  account,
  templates,
  onBack,
  onClose,
  onSaved,
}: Params) {
  const [draft, setDraft] = useState(() => initialDraft(account, templates));
  const [baseline, setBaseline] = useState(() =>
    initialDraft(account, templates),
  );
  const [rawJson, setRawJson] = useState(() =>
    formatApiAccountConfig(initialDraft(account, templates).advancedConfig),
  );
  const [jsonError, setJsonError] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] =
    useState<ApiAccountDraftValidationResponse | null>(null);
  const [activeSection, setActiveSection] =
    useState<ApiAccountSection>("identity");
  const preset = providerPresetMap.get(draft.provider) ?? firstPreset;
  const editing = account !== null;
  const dirty =
    stableApiAccountConfig(draft) !== stableApiAccountConfig(baseline);

  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const updateDraft = useCallback(
    (fields: Partial<ApiAccountWorkspaceDraft>) => {
      setDraft((previous) => ({ ...previous, ...fields }));
    },
    [],
  );

  const updateAdvanced = useCallback(
    (fields: Parameters<typeof updateApiAccountConfig>[1]) => {
      setDraft((previous) => {
        const advancedConfig = updateApiAccountConfig(
          previous.advancedConfig,
          fields,
        );
        if (!jsonError) setRawJson(formatApiAccountConfig(advancedConfig));
        return { ...previous, advancedConfig };
      });
    },
    [jsonError],
  );

  const leave = useCallback(
    (callback: () => void) => {
      if (saving) return;
      if (dirty && !window.confirm("当前配置尚未保存，确认离开？")) return;
      callback();
    },
    [dirty, saving],
  );

  const selectProvider = useCallback(
    (provider: string) => {
      if (saving || editing) return;
      const next = providerPresetMap.get(provider) ?? firstPreset;
      setDraft((previous) => {
        const old = providerPresetMap.get(previous.provider) ?? firstPreset;
        const manual =
          (previous.baseUrl && previous.baseUrl !== old.baseUrl) ||
          (previous.model && previous.model !== old.model) ||
          (previous.websiteUrl && previous.websiteUrl !== old.websiteUrl);
        const restore = manual
          ? window.confirm(
              "已手动修改连接配置。确定恢复为新服务商默认值？取消将保留手动值。",
            )
          : true;
        const advancedConfig = updateApiAccountConfig(previous.advancedConfig, {
          fallback_model:
            restore || previous.advancedConfig.fallback_model === old.model
              ? next.model
              : previous.advancedConfig.fallback_model,
        });
        if (!jsonError) setRawJson(formatApiAccountConfig(advancedConfig));
        return {
          ...previous,
          provider: next.provider,
          baseUrl:
            restore || previous.baseUrl === old.baseUrl
              ? next.baseUrl
              : previous.baseUrl,
          model:
            restore || previous.model === old.model
              ? next.model
              : previous.model,
          websiteUrl:
            restore || previous.websiteUrl === old.websiteUrl
              ? next.websiteUrl
              : previous.websiteUrl,
          protocol: next.protocol,
          authScheme: next.authScheme,
          advancedConfig,
          thinkingMode: "off",
        };
      });
    },
    [editing, jsonError, saving],
  );

  const locate = useCallback(
    (section: ApiAccountSection, id: string, message: string) => {
      setActiveSection(section);
      setError(message);
      document.getElementById(id)?.focus();
      return false;
    },
    [],
  );

  const validateLocal = useCallback(() => {
    if (!editing && !draft.apiKey.trim())
      return locate("connection", "api-account-api-key", "请填写 API Key");
    if (!draft.baseUrl.trim())
      return locate("connection", "api-account-base-url", "请填写 Base URL");
    if (preset.kind === "llm" && !draft.model.trim())
      return locate("models", "api-account-model", "请填写模型");
    const aliases = draft.modelMappingRows.map((row) => row.alias.trim());
    if (
      draft.modelMappingRows.some(
        (row) => !row.alias.trim() || !row.model.trim(),
      ) ||
      new Set(aliases).size !== aliases.length
    )
      return locate(
        "models",
        "api-account-model-mapping",
        "模型映射别名和值不能为空或重复",
      );
    if (draft.headerRows.some((row) => !row.name.trim()))
      return locate("request", "api-account-headers", "Header 名称不能为空");
    try {
      payload(draft, templates);
    } catch (value) {
      return locate(
        "request",
        "api-account-headers",
        value instanceof Error ? value.message : "请求覆盖配置无效",
      );
    }
    try {
      thinkingConfig(draft, templates);
    } catch {
      return locate(
        "request",
        "api-account-thinking",
        "思考配置 JSON 格式错误",
      );
    }
    setError("");
    return true;
  }, [draft, editing, locate, preset.kind, templates]);

  const buildPayload = useCallback(() => {
    const result = payload(draft, templates);
    const apiKey = draft.apiKey.trim();
    return apiKey ? { ...result, api_key: apiKey } : result;
  }, [draft, templates]);

  const save = useCallback(async () => {
    if (saving || !validateLocal()) return;
    setSaving(true);
    setError("");
    try {
      const current = buildPayload();
      if (editing && draft.accountId !== null)
        await apiAccountApi.update(draft.accountId, current);
      else
        await apiAccountApi.create({
          ...current,
          api_key: draft.apiKey.trim(),
        });
      setBaseline(draft);
      onSaved();
    } catch (value) {
      setError(value instanceof Error ? value.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [buildPayload, draft, editing, onSaved, saving, validateLocal]);

  const validateDraft = useCallback(async () => {
    if (validating || !validateLocal()) return;
    setValidating(true);
    setValidation(null);
    try {
      setValidation(
        await apiAccountApi.validateDraft({
          ...buildPayload(),
          account_id: draft.accountId ?? undefined,
        }),
      );
    } catch (value) {
      setError(value instanceof Error ? value.message : "连接测试失败");
    } finally {
      setValidating(false);
    }
  }, [buildPayload, draft.accountId, validateLocal, validating]);

  const applyJson = useCallback(
    (raw = rawJson) => {
      try {
        const advancedConfig = parseApiAccountConfig(raw);
        setDraft((previous) => ({
          ...previous,
          advancedConfig,
          modelMappingRows: Object.entries(advancedConfig.model_mapping).map(
            ([alias, model], index) => ({ id: `model-${index}`, alias, model }),
          ),
          headerRows: Object.entries(advancedConfig.headers).map(
            ([name, value], index) => ({ id: `header-${index}`, name, value }),
          ),
          bodyRaw: JSON.stringify(advancedConfig.body, null, 2),
        }));
        setRawJson(formatApiAccountConfig(advancedConfig));
        setJsonError("");
        return true;
      } catch (value) {
        const configError = value as ApiAccountConfigError;
        setJsonError(configError.message);
        setActiveSection("json");
        return false;
      }
    },
    [rawJson],
  );

  return {
    draft,
    preset,
    editing,
    dirty,
    rawJson,
    jsonError,
    error,
    saving,
    validating,
    validation,
    activeSection,
    setActiveSection,
    setRawJson,
    setJsonError,
    updateDraft,
    updateAdvanced,
    selectProvider,
    applyJson,
    save,
    validateDraft,
    back: () => leave(onBack),
    close: () => leave(onClose),
  };
}
