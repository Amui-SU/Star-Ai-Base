"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  apiAccountApi,
  chatApi,
  type ApiAccount,
  type ApiAccountCreateRequest,
  type ApiAccountUpdateRequest,
} from "@/lib/api";
import { PROVIDER_PRESETS, providerPresetMap } from "@/lib/providers";
import {
  formatThinkingConfig,
  inferThinkingMode,
  parseThinkingConfig,
  type ThinkingConfig,
} from "@/lib/thinkingConfig";
import type {
  ApiAccountEditorTab,
  ApiAccountFormState,
  ApiAccountsPanelView,
  ThinkingTemplates,
} from "./types";

const firstProvider = PROVIDER_PRESETS[0];

const emptyForm = (): ApiAccountFormState => ({
  accountId: null,
  provider: firstProvider.provider,
  displayName: "",
  apiKey: "",
  baseUrl: firstProvider.baseUrl,
  model: firstProvider.model,
  enabled: true,
  isDefault: false,
  thinkingMode: "off",
  thinkingJson: "{}",
});

interface UseApiAccountsPanelParams {
  open: boolean;
  onChanged?: () => void;
}

export function useApiAccountsPanel({
  open,
  onChanged,
}: UseApiAccountsPanelParams) {
  const [accounts, setAccounts] = useState<ApiAccount[]>([]);
  const [view, setView] = useState<ApiAccountsPanelView>("list");
  const [activeTab, setActiveTab] = useState<ApiAccountEditorTab>("basic");
  const [templates, setTemplates] = useState<ThinkingTemplates>({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [thinkingError, setThinkingError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<ApiAccountFormState>(emptyForm);

  const selectedPreset = useMemo(
    () => providerPresetMap.get(form.provider) ?? firstProvider,
    [form.provider],
  );
  const selectedTemplate = templates[form.provider] ?? {};
  const editing = view === "edit";
  const isSearchProvider = form.provider === "tavily";

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setAccounts(await apiAccountApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 服务密钥加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      const config = await chatApi.getModelConfig();
      setTemplates(
        Object.fromEntries(
          config.providers.map((provider) => [
            provider.provider,
            provider.thinking_template ?? {},
          ]),
        ),
      );
    } catch {
      setTemplates({});
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setView("list");
      setActiveTab("basic");
      setNotice("");
      setError("");
      setThinkingError("");
      setForm(emptyForm());
      void loadAccounts();
      void loadTemplates();
    });
    return () => {
      cancelled = true;
    };
  }, [loadAccounts, loadTemplates, open]);

  const selectProvider = (provider: string) => {
    const preset = providerPresetMap.get(provider) ?? firstProvider;
    setForm((prev) => ({
      ...prev,
      provider: preset.provider,
      baseUrl: preset.baseUrl,
      model: preset.model,
      displayName: "",
      thinkingMode: "off",
    }));
    setThinkingError("");
    setActiveTab("basic");
  };

  const createAccount = () => {
    setNotice("");
    setError("");
    setThinkingError("");
    setForm(emptyForm());
    setActiveTab("basic");
    setView("create");
  };

  const editAccount = (account: ApiAccount) => {
    const template = templates[account.provider] ?? {};
    setNotice("");
    setError("");
    setThinkingError("");
    setForm({
      accountId: account.id,
      provider: account.provider,
      displayName: account.display_name,
      apiKey: "",
      baseUrl: account.base_url,
      model: account.model,
      enabled: account.enabled,
      isDefault: account.is_default,
      thinkingMode: inferThinkingMode(account.thinking_config, template),
      thinkingJson: formatThinkingConfig(account.thinking_config),
    });
    setActiveTab("basic");
    setView("edit");
  };

  const returnToList = () => {
    setError("");
    setThinkingError("");
    setActiveTab("basic");
    setView("list");
  };

  const notifyChanged = async (message: string) => {
    await loadAccounts();
    onChanged?.();
    setNotice(message);
  };

  const getThinkingConfig = (): ThinkingConfig | null => {
    if (form.thinkingMode === "off") return {};
    if (form.thinkingMode === "standard") return selectedTemplate;
    try {
      return parseThinkingConfig(form.thinkingJson);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "思考配置 JSON 格式错误";
      setThinkingError(message);
      setError(message);
      setActiveTab("request");
      return null;
    }
  };

  const saveAccount = async () => {
    const apiKey = form.apiKey.trim();
    if (!editing && !apiKey) {
      setError("请填写 API Key");
      return;
    }
    if (!form.baseUrl.trim()) {
      setError("请填写 Base URL");
      return;
    }
    if (!form.model.trim()) {
      setError("请填写模型或服务名称");
      return;
    }
    const thinkingConfig = isSearchProvider ? {} : getThinkingConfig();
    if (thinkingConfig === null) return;

    setSaving(true);
    setError("");
    setThinkingError("");
    try {
      if (editing && form.accountId !== null) {
        const payload: ApiAccountUpdateRequest = {
          display_name: form.displayName.trim() || selectedPreset.label,
          base_url: form.baseUrl.trim(),
          model: form.model.trim(),
          thinking_config: thinkingConfig,
          enabled: form.enabled,
          is_default: form.isDefault,
        };
        if (apiKey) payload.api_key = apiKey;
        await apiAccountApi.update(form.accountId, payload);
        returnToList();
        await notifyChanged("AI 服务密钥已更新");
      } else {
        const payload: ApiAccountCreateRequest = {
          provider: form.provider,
          display_name: form.displayName.trim() || selectedPreset.label,
          api_key: apiKey,
          base_url: form.baseUrl.trim(),
          model: form.model.trim(),
          thinking_config: thinkingConfig,
          is_default: form.isDefault,
        };
        await apiAccountApi.create(payload);
        returnToList();
        await notifyChanged("AI 服务密钥已添加");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 服务密钥保存失败");
    } finally {
      setSaving(false);
    }
  };

  const setDefault = async (account: ApiAccount) => {
    setBusyId(account.id);
    setError("");
    try {
      await apiAccountApi.setDefault(account.id);
      await notifyChanged("默认密钥已切换");
    } catch (err) {
      setError(err instanceof Error ? err.message : "默认密钥切换失败");
    } finally {
      setBusyId(null);
    }
  };

  const validateAccount = async (account: ApiAccount) => {
    setBusyId(account.id);
    setError("");
    try {
      await apiAccountApi.validate(account.id);
      await notifyChanged("密钥已标记为可用");
    } catch (err) {
      setError(err instanceof Error ? err.message : "密钥验证失败");
    } finally {
      setBusyId(null);
    }
  };

  const removeAccount = async (account: ApiAccount) => {
    if (!window.confirm(`删除 ${account.display_name}？`)) return;
    setBusyId(account.id);
    setError("");
    try {
      await apiAccountApi.remove(account.id);
      await notifyChanged("AI 服务密钥已删除");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 服务密钥删除失败");
    } finally {
      setBusyId(null);
    }
  };

  return {
    accounts,
    activeTab,
    busyId,
    createAccount,
    editAccount,
    editing,
    error,
    form,
    isSearchProvider,
    loadAccounts,
    loading,
    notice,
    removeAccount,
    returnToList,
    saveAccount,
    saving,
    selectedPreset,
    selectedTemplate,
    selectProvider,
    setActiveTab,
    setDefault,
    setForm,
    setThinkingError,
    thinkingError,
    validateAccount,
    view,
  };
}
