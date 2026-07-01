"use client";

import { useEffect, useMemo, useState } from "react";
import {
  apiAccountApi,
  type ApiAccount,
  type ApiAccountCreateRequest,
  type ApiAccountUpdateRequest,
} from "@/lib/api";
import { PROVIDER_PRESETS, providerPresetMap } from "@/lib/providers";

const firstProvider = PROVIDER_PRESETS[0];

const emptyForm = () => ({
  accountId: null as number | null,
  provider: firstProvider.provider,
  displayName: "",
  apiKey: "",
  baseUrl: firstProvider.baseUrl,
  model: firstProvider.model,
  enabled: true,
  isDefault: false,
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
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState(emptyForm);

  const selectedPreset = useMemo(
    () => providerPresetMap.get(form.provider) ?? firstProvider,
    [form.provider],
  );
  const editing = form.accountId !== null;
  const isSearchProvider = form.provider === "tavily";

  const loadAccounts = async () => {
    setLoading(true);
    setError("");
    try {
      const nextAccounts = await apiAccountApi.list();
      setAccounts(nextAccounts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 服务密钥加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setNotice("");
      setError("");
      setForm(emptyForm());
      void loadAccounts();
    });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const selectProvider = (provider: string) => {
    const preset = providerPresetMap.get(provider) ?? firstProvider;
    setForm((prev) => ({
      ...prev,
      provider: preset.provider,
      baseUrl: preset.baseUrl,
      model: preset.model,
      displayName: prev.accountId ? prev.displayName : "",
    }));
  };

  const editAccount = (account: ApiAccount) => {
    setNotice("");
    setError("");
    setForm({
      accountId: account.id,
      provider: account.provider,
      displayName: account.display_name,
      apiKey: "",
      baseUrl: account.base_url,
      model: account.model,
      enabled: account.enabled,
      isDefault: account.is_default,
    });
  };

  const resetForm = () => {
    setNotice("");
    setError("");
    setForm(emptyForm());
  };

  const notifyChanged = async (message: string) => {
    await loadAccounts();
    onChanged?.();
    setNotice(message);
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
    setSaving(true);
    setError("");
    try {
      if (editing && form.accountId !== null) {
        const payload: ApiAccountUpdateRequest = {
          display_name: form.displayName.trim() || selectedPreset.label,
          base_url: form.baseUrl.trim(),
          model: form.model.trim(),
          enabled: form.enabled,
          is_default: form.isDefault,
        };
        if (apiKey) payload.api_key = apiKey;
        await apiAccountApi.update(form.accountId, payload);
        await notifyChanged("AI 服务密钥已更新");
      } else {
        const payload: ApiAccountCreateRequest = {
          provider: form.provider,
          display_name: form.displayName.trim() || selectedPreset.label,
          api_key: apiKey,
          base_url: form.baseUrl.trim(),
          model: form.model.trim(),
          is_default: form.isDefault,
        };
        await apiAccountApi.create(payload);
        await notifyChanged("AI 服务密钥已添加");
      }
      resetForm();
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
    const confirmed = window.confirm(`删除 ${account.display_name}？`);
    if (!confirmed) return;
    setBusyId(account.id);
    setError("");
    try {
      await apiAccountApi.remove(account.id);
      await notifyChanged("AI 服务密钥已删除");
      if (form.accountId === account.id) resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 服务密钥删除失败");
    } finally {
      setBusyId(null);
    }
  };

  return {
    accounts,
    busyId,
    editAccount,
    editing,
    error,
    form,
    isSearchProvider,
    loadAccounts,
    loading,
    notice,
    removeAccount,
    resetForm,
    saveAccount,
    saving,
    selectedPreset,
    selectProvider,
    setDefault,
    setForm,
    validateAccount,
  };
}
