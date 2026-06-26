"use client";

import type { WebSearchConfigResponse } from "@/lib/api";
import ModalShell from "@/components/ui/ModalShell";

interface WebSearchConfigModalProps {
  config: WebSearchConfigResponse | null;
  apiKey: string;
  saving: boolean;
  error: string;
  onApiKeyChange: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export default function WebSearchConfigModal({
  config,
  apiKey,
  saving,
  error,
  onApiKeyChange,
  onClose,
  onSave,
}: WebSearchConfigModalProps) {
  return (
    <ModalShell cardClassName="thinking-provider-modal" onClose={onClose}>
      <div className="provider-config-head">
        <div className="provider-config-title-block">
          <h3 className="provider-config-title">配置联网搜索</h3>
          <p className="provider-config-subtitle">
            Tavily API Key 会写入后端 .env.local，前端只保存是否已配置。{" "}
          </p>
        </div>
        <button
          type="button"
          className="provider-config-close"
          onClick={onClose}
          disabled={saving}
          aria-label="关闭联网搜索配置"
        >
          x
        </button>
      </div>

      <div className="provider-config-body">
        <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
          Tavily API Key
          <input
            type="password"
            value={apiKey}
            onChange={(event) => onApiKeyChange(event.target.value)}
            className="input provider-config-input text-center"
            placeholder={
              config?.tavily_configured
                ? "留空沿用已保存的 Tavily API Key"
                : "粘贴 Tavily API Key"
            }
            autoFocus
          />
        </label>

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
    </ModalShell>
  );
}
