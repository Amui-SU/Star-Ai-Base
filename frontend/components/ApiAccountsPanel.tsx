"use client";

import { useEffect, useMemo, useState } from "react";
import {
  apiAccountApi,
  type ApiAccount,
  type ApiAccountCreateRequest,
  type ApiAccountUpdateRequest,
} from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

type ProviderPreset = {
  provider: string;
  label: string;
  baseUrl: string;
  model: string;
};

const PROVIDERS: ProviderPreset[] = [
  {
    provider: "deepseek",
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
  },
  {
    provider: "dashscope",
    label: "阿里云 DashScope",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-max",
  },
  {
    provider: "openai",
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  },
  {
    provider: "kimi",
    label: "Moonshot Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
  },
  {
    provider: "siliconflow",
    label: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    model: "Qwen/Qwen2.5-7B-Instruct",
  },
  {
    provider: "zhipu",
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
  },
  {
    provider: "tavily",
    label: "Tavily 搜索",
    baseUrl: "https://api.tavily.com",
    model: "tavily-search",
  },
];

const providerMap = new Map(
  PROVIDERS.map((provider) => [provider.provider, provider]),
);

const firstProvider = PROVIDERS[0];

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

export default function ApiAccountsPanel({ open, onClose, onChanged }: Props) {
  const [accounts, setAccounts] = useState<ApiAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState(emptyForm);

  const selectedPreset = useMemo(
    () => providerMap.get(form.provider) ?? firstProvider,
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

  if (!open) return null;

  const selectProvider = (provider: string) => {
    const preset = providerMap.get(provider) ?? firstProvider;
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

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal-card api-accounts-panel"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="provider-config-head">
          <div className="provider-config-title-block">
            <div className="provider-config-title">AI 服务密钥</div>
            <div className="provider-config-subtitle">
              每个用户独立保存第三方模型或搜索服务 Key，Key
              只写入后端，不会在前端回显。
            </div>
          </div>
          <button
            type="button"
            className="provider-config-close"
            onClick={onClose}
            aria-label="关闭 AI 服务密钥管理"
          >
            x
          </button>
        </div>

        <div className="api-accounts-layout">
          <section className="api-accounts-list" aria-label="AI 服务密钥列表">
            <div className="api-accounts-toolbar">
              <span>{loading ? "加载中..." : `${accounts.length} 个密钥`}</span>
              <button
                type="button"
                className="admin-users-secondary"
                onClick={() => void loadAccounts()}
                disabled={loading}
              >
                刷新
              </button>
            </div>

            {accounts.length === 0 && !loading ? (
              <div className="api-accounts-empty">还没有 AI 服务密钥</div>
            ) : (
              accounts.map((account) => (
                <article
                  key={account.id}
                  className={`api-account-row ${
                    form.accountId === account.id ? "active" : ""
                  }`}
                >
                  <button
                    type="button"
                    className="api-account-main"
                    onClick={() => editAccount(account)}
                  >
                    <span className="api-account-name">
                      {account.display_name}
                    </span>
                    <span className="api-account-meta">
                      {account.provider_label} / {account.model}
                    </span>
                  </button>
                  <div className="api-account-badges">
                    {account.is_default && <span>默认</span>}
                    <span className={account.enabled ? "active" : "inactive"}>
                      {account.enabled ? "启用" : "停用"}
                    </span>
                  </div>
                  <div className="api-account-actions">
                    <button
                      type="button"
                      className="admin-users-secondary"
                      onClick={() => void setDefault(account)}
                      disabled={account.is_default || busyId === account.id}
                    >
                      设默认
                    </button>
                    <button
                      type="button"
                      className="admin-users-secondary"
                      onClick={() => void validateAccount(account)}
                      disabled={busyId === account.id}
                    >
                      验证
                    </button>
                    <button
                      type="button"
                      className="admin-users-secondary danger"
                      onClick={() => void removeAccount(account)}
                      disabled={busyId === account.id}
                    >
                      删除
                    </button>
                  </div>
                  {account.last_error && (
                    <div className="api-account-error">
                      {account.last_error}
                    </div>
                  )}
                </article>
              ))
            )}
          </section>

          <section className="api-account-form" aria-label="AI 服务密钥表单">
            <div className="api-account-form-head">
              <div>
                <div className="api-account-form-title">
                  {editing ? "编辑密钥" : "添加密钥"}
                </div>
                <div className="api-account-form-subtitle">
                  {editing
                    ? "Key 留空表示沿用已保存的 Key"
                    : "选择服务商并填写自己的 Key"}
                </div>
              </div>
              {editing && (
                <button
                  type="button"
                  className="admin-users-secondary"
                  onClick={resetForm}
                >
                  新增
                </button>
              )}
            </div>

            <label className="api-account-field">
              <span>服务商</span>
              <select
                className="input"
                value={form.provider}
                disabled={editing}
                onChange={(event) => selectProvider(event.target.value)}
              >
                {PROVIDERS.map((provider) => (
                  <option key={provider.provider} value={provider.provider}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="api-account-field">
              <span>密钥名称</span>
              <input
                className="input"
                value={form.displayName}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    displayName: event.target.value,
                  }))
                }
                placeholder={selectedPreset.label}
              />
            </label>

            <label className="api-account-field">
              <span>API Key</span>
              <input
                className="input"
                type="password"
                value={form.apiKey}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, apiKey: event.target.value }))
                }
                placeholder={editing ? "留空沿用已保存的 Key" : "粘贴 API Key"}
              />
            </label>

            <label className="api-account-field">
              <span>{isSearchProvider ? "服务地址" : "Base URL"}</span>
              <input
                className="input"
                value={form.baseUrl}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    baseUrl: event.target.value,
                  }))
                }
              />
            </label>

            <label className="api-account-field">
              <span>{isSearchProvider ? "服务名称" : "模型"}</span>
              <input
                className="input"
                value={form.model}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, model: event.target.value }))
                }
              />
            </label>

            <div className="api-account-switches">
              <label>
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      enabled: event.target.checked,
                    }))
                  }
                />
                启用
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={form.isDefault}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      isDefault: event.target.checked,
                    }))
                  }
                />
                设为默认
              </label>
            </div>

            {(error || notice) && (
              <div
                className={`api-account-message ${error ? "error" : ""}`}
                role="status"
              >
                {error || notice}
              </div>
            )}

            <div className="provider-config-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={onClose}
                disabled={saving}
              >
                关闭
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void saveAccount()}
                disabled={saving}
              >
                {saving ? "保存中..." : editing ? "保存修改" : "添加密钥"}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
