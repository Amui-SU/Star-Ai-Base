"use client";

import { formatThinkingConfig, type ThinkingMode } from "@/lib/thinkingConfig";
import type { ModelConfigProvider } from "@/components/chat/types";

interface ModelConfigModalProps {
  provider: ModelConfigProvider;
  apiKey: string;
  baseUrl: string;
  model: string;
  thinkingMode: ThinkingMode;
  thinkingJson: string;
  saving: boolean;
  error: string;
  onApiKeyChange: (value: string) => void;
  onBaseUrlChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onThinkingModeChange: (mode: ThinkingMode, json: string) => void;
  onThinkingJsonChange: (value: string) => void;
  onClearError: () => void;
  onClose: () => void;
  onSave: () => void;
}

export default function ModelConfigModal({
  provider,
  apiKey,
  baseUrl,
  model,
  thinkingMode,
  thinkingJson,
  saving,
  error,
  onApiKeyChange,
  onBaseUrlChange,
  onModelChange,
  onThinkingModeChange,
  onThinkingJsonChange,
  onClearError,
  onClose,
  onSave,
}: ModelConfigModalProps) {
  const handleThinkingModeClick = (mode: ThinkingMode) => {
    let nextJson = thinkingJson;
    if (mode === "off") {
      nextJson = "{}";
    } else if (mode === "standard") {
      nextJson = formatThinkingConfig(provider.thinking_template || {});
    } else if (thinkingJson === "{}") {
      nextJson = formatThinkingConfig(provider.thinking_template || {});
    }
    onThinkingModeChange(mode, nextJson);
    onClearError();
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal-card thinking-provider-modal"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="provider-config-head">
          <div className="provider-config-title-block">
            <h3 className="provider-config-title">配置 {provider.label}</h3>
            <p className="provider-config-subtitle">
              保存后会写入项目的 .env.local，并自动切换到该模型。
            </p>
          </div>
          <button
            type="button"
            className="provider-config-close"
            onClick={onClose}
            disabled={saving}
            aria-label="关闭配置弹窗"
          >
            ×
          </button>
        </div>

        <div className="provider-config-body">
          <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => onApiKeyChange(event.target.value)}
              className="input provider-config-input text-center"
              placeholder={
                provider.enabled
                  ? "留空沿用已保存的 API Key"
                  : "粘贴对应平台的 API Key"
              }
              autoFocus
            />
          </label>

          <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
            Base URL
            <input
              type="text"
              value={baseUrl}
              onChange={(event) => onBaseUrlChange(event.target.value)}
              className="input provider-config-input"
              placeholder="留空使用默认地址"
            />
          </label>

          <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
            模型名称
            <input
              type="text"
              value={model}
              onChange={(event) => onModelChange(event.target.value)}
              className="input provider-config-input"
              placeholder={provider.model}
            />
          </label>

          <fieldset className="thinking-config-fieldset">
            <legend>思考配置</legend>
            <div className="thinking-mode-options">
              {(
                [
                  ["off", "关闭"],
                  ["standard", "标准模板"],
                  ["custom", "自定义 JSON"],
                ] as const
              ).map(([mode, label]) => (
                <button
                  key={mode}
                  type="button"
                  className={`thinking-mode-option ${
                    thinkingMode === mode ? "active" : ""
                  }`}
                  onClick={() => handleThinkingModeClick(mode)}
                  disabled={
                    mode === "standard" &&
                    Object.keys(provider.thinking_template || {}).length === 0
                  }
                >
                  {label}
                </button>
              ))}
            </div>

            {thinkingMode !== "off" && (
              <label className="thinking-json-editor">
                <span>
                  请求体 JSON
                  {thinkingMode === "standard" && "（标准模板）"}
                </span>
                <textarea
                  value={thinkingJson}
                  onChange={(event) => onThinkingJsonChange(event.target.value)}
                  readOnly={thinkingMode === "standard"}
                  spellCheck={false}
                  rows={7}
                  wrap="soft"
                />
              </label>
            )}
            <p className="thinking-config-help">
              保存时会发送最小测试请求。验证成功后才写入
              .env.local，并自动应用到后续对话。
            </p>
          </fieldset>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}
        </div>

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
      </div>
    </div>
  );
}
