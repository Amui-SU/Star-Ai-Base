import type { Dispatch, SetStateAction } from "react";

import { PROVIDER_PRESETS, type ProviderPreset } from "@/lib/providers";

interface ApiAccountFormState {
  accountId: number | null;
  provider: string;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  enabled: boolean;
  isDefault: boolean;
}

interface ApiAccountFormProps {
  editing: boolean;
  error: string;
  form: ApiAccountFormState;
  isSearchProvider: boolean;
  notice: string;
  saving: boolean;
  selectedPreset: ProviderPreset;
  setForm: Dispatch<SetStateAction<ApiAccountFormState>>;
  onClose: () => void;
  onResetForm: () => void;
  onSave: () => void;
  onSelectProvider: (provider: string) => void;
}

export default function ApiAccountForm({
  editing,
  error,
  form,
  isSearchProvider,
  notice,
  saving,
  selectedPreset,
  setForm,
  onClose,
  onResetForm,
  onSave,
  onSelectProvider,
}: ApiAccountFormProps) {
  return (
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
            onClick={onResetForm}
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
          onChange={(event) => onSelectProvider(event.target.value)}
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
          onClick={onSave}
          disabled={saving}
        >
          {saving ? "保存中..." : editing ? "保存修改" : "添加密钥"}
        </button>
      </div>
    </section>
  );
}
