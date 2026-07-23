import type { Dispatch, SetStateAction } from "react";

import { ApiCredentialEditorShell } from "@/components/api-credentials/ApiCredentialEditorShell";
import { ThinkingConfigEditor } from "@/components/api-credentials/ThinkingConfigEditor";
import { PROVIDER_PRESETS, type ProviderPreset } from "@/lib/providers";
import type { ThinkingConfig } from "@/lib/thinkingConfig";
import type { ApiAccountEditorTab, ApiAccountFormState } from "./types";

interface ApiAccountFormProps {
  activeTab: ApiAccountEditorTab;
  editing: boolean;
  error: string;
  form: ApiAccountFormState;
  isSearchProvider: boolean;
  saving: boolean;
  selectedPreset: ProviderPreset;
  selectedTemplate: ThinkingConfig;
  thinkingError: string;
  setForm: Dispatch<SetStateAction<ApiAccountFormState>>;
  onBack: () => void;
  onClose: () => void;
  onSave: () => void;
  onSelectProvider: (provider: string) => void;
  onTabChange: (tab: ApiAccountEditorTab) => void;
  onThinkingErrorChange: (error: string) => void;
}

export default function ApiAccountForm({
  activeTab,
  editing,
  error,
  form,
  isSearchProvider,
  saving,
  selectedPreset,
  selectedTemplate,
  thinkingError,
  setForm,
  onBack,
  onClose,
  onSave,
  onSelectProvider,
  onTabChange,
  onThinkingErrorChange,
}: ApiAccountFormProps) {
  const basicContent = (
    <>
      <div className="api-account-basic-grid">
        <label className="api-account-field">
          <span>服务商</span>
          <select
            className="input"
            aria-label="服务商"
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
              setForm((prev) => ({ ...prev, baseUrl: event.target.value }))
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
      </div>

      <div className="api-account-switches">
        {editing ? (
          <label>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, enabled: event.target.checked }))
              }
            />
            启用
          </label>
        ) : null}
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

      {error ? (
        <div className="api-account-message error" role="status">
          {error}
        </div>
      ) : null}
    </>
  );

  const requestContent = isSearchProvider ? undefined : (
    <ThinkingConfigEditor
      mode={form.thinkingMode}
      customJson={form.thinkingJson}
      template={selectedTemplate}
      error={thinkingError}
      onModeChange={(thinkingMode) =>
        setForm((prev) => ({ ...prev, thinkingMode }))
      }
      onCustomJsonChange={(thinkingJson) =>
        setForm((prev) => ({ ...prev, thinkingJson }))
      }
      onErrorChange={onThinkingErrorChange}
    />
  );

  return (
    <ApiCredentialEditorShell
      title={editing ? "编辑密钥" : "添加密钥"}
      subtitle={
        editing
          ? "API Key 留空表示沿用已保存的 Key"
          : "选择服务商并填写自己的 Key"
      }
      activeTab={activeTab}
      showRequestTab={!isSearchProvider}
      saving={saving}
      onBack={onBack}
      onClose={onClose}
      onTabChange={onTabChange}
      basicContent={basicContent}
      requestContent={requestContent}
      footer={
        <div className="provider-config-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onBack}
            disabled={saving}
          >
            取消
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
      }
    />
  );
}
