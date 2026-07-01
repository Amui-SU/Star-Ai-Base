"use client";

import { PROVIDER_PRESETS } from "@/lib/providers";
import { useApiAccountsPanel } from "@/components/api-accounts/useApiAccountsPanel";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export default function ApiAccountsPanel({ open, onClose, onChanged }: Props) {
  const {
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
  } = useApiAccountsPanel({ open, onChanged });

  if (!open) return null;

  return (
    <ModalShell cardClassName="api-accounts-panel" onClose={onClose}>
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
                  <div className="api-account-error">{account.last_error}</div>
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
              {PROVIDER_PRESETS.map((provider) => (
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
    </ModalShell>
  );
}
