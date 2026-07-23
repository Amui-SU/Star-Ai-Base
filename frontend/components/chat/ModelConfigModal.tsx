"use client";

import {
  ApiCredentialEditorShell,
  type ApiCredentialEditorTab,
} from "@/components/api-credentials/ApiCredentialEditorShell";
import { ThinkingConfigEditor } from "@/components/api-credentials/ThinkingConfigEditor";
import type { ModelConfigProvider } from "@/components/chat/types";
import ModalShell from "@/components/ui/ModalShell";
import type { ThinkingMode } from "@/lib/thinkingConfig";

interface ModelConfigModalProps {
  provider: ModelConfigProvider;
  apiKey: string;
  baseUrl: string;
  model: string;
  activeTab: ApiCredentialEditorTab;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
  saving: boolean;
  error: string;
  onApiKeyChange: (value: string) => void;
  onBaseUrlChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onTabChange: (tab: ApiCredentialEditorTab) => void;
  onThinkingModeChange: (mode: ThinkingMode) => void;
  onThinkingJsonChange: (value: string) => void;
  onErrorChange: (error: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export default function ModelConfigModal({
  provider,
  apiKey,
  baseUrl,
  model,
  activeTab,
  thinkingMode,
  thinkingJson,
  saving,
  error,
  onApiKeyChange,
  onBaseUrlChange,
  onModelChange,
  onTabChange,
  onThinkingModeChange,
  onThinkingJsonChange,
  onErrorChange,
  onClose,
  onSave,
}: ModelConfigModalProps) {
  const basicContent = (
    <div className="provider-config-fields">
      <label>
        <span>API Key</span>
        <input
          type="password"
          value={apiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          className="input provider-config-input"
          placeholder={
            provider.enabled
              ? "留空沿用已保存的 API Key"
              : "粘贴对应平台的 API Key"
          }
          autoFocus
        />
      </label>
      <label>
        <span>Base URL</span>
        <input
          type="text"
          value={baseUrl}
          onChange={(event) => onBaseUrlChange(event.target.value)}
          className="input provider-config-input"
          placeholder="留空使用默认地址"
        />
      </label>
      <label>
        <span>模型名称</span>
        <input
          type="text"
          value={model}
          onChange={(event) => onModelChange(event.target.value)}
          className="input provider-config-input"
          placeholder={provider.model}
        />
      </label>
      {activeTab === "basic" && error ? (
        <p className="provider-config-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );

  const requestContent = (
    <ThinkingConfigEditor
      mode={thinkingMode}
      customJson={thinkingJson}
      template={provider.thinking_template || {}}
      error={activeTab === "request" ? error : ""}
      onModeChange={(mode) => {
        onThinkingModeChange(mode);
        onErrorChange("");
      }}
      onCustomJsonChange={(value) => {
        onThinkingJsonChange(value);
        onErrorChange("");
      }}
      onErrorChange={onErrorChange}
    />
  );

  return (
    <ModalShell cardClassName="thinking-provider-modal" onClose={onClose}>
      <ApiCredentialEditorShell
        title={`配置 ${provider.label}`}
        subtitle="保存前会验证连接，成功后自动应用到后续对话。"
        activeTab={activeTab}
        showRequestTab
        saving={saving}
        onClose={onClose}
        onTabChange={onTabChange}
        basicContent={basicContent}
        requestContent={requestContent}
        footer={
          <div className="provider-config-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
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
              {saving ? "保存中..." : "保存配置"}
            </button>
          </div>
        }
      />
    </ModalShell>
  );
}
