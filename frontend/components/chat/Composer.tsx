"use client";

import ChatScopePicker from "@/components/ChatScopePicker";
import type {
  KnowledgeScopeOptions,
  WebSearchConfigResponse,
  WebSearchProvider,
} from "@/lib/api";
import type { ChatScopeSelection } from "@/lib/chatScope";

interface ComposerProps {
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  input: string;
  knowledgeBaseId?: number | null;
  isGenerating: boolean;
  canSend: boolean;
  scopeOptions: KnowledgeScopeOptions;
  chatScope: ChatScopeSelection;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  webSearchConfig: WebSearchConfigResponse | null;
  canConfigureWebSearch: boolean;
  webSearchNotice: string;
  onInputChange: (value: string, element: HTMLTextAreaElement) => void;
  onSend: () => void;
  onStopGenerating: () => void;
  onScopeChange: (next: ChatScopeSelection) => void;
  onWebSearchChange: (enabled: boolean) => void;
  onWebSearchProviderChange: (provider: WebSearchProvider) => void;
  onConfigureTavily: () => void;
}

export default function Composer({
  inputRef,
  input,
  knowledgeBaseId,
  isGenerating,
  canSend,
  scopeOptions,
  chatScope,
  webSearchEnabled,
  webSearchProvider,
  webSearchConfig,
  canConfigureWebSearch,
  webSearchNotice,
  onInputChange,
  onSend,
  onStopGenerating,
  onScopeChange,
  onWebSearchChange,
  onWebSearchProviderChange,
  onConfigureTavily,
}: ComposerProps) {
  return (
    <div className="relative composer-shell">
      <textarea
        ref={inputRef}
        value={input}
        onChange={(e) => onInputChange(e.target.value, e.target)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (isGenerating) {
              onStopGenerating();
            } else {
              onSend();
            }
          }
        }}
        placeholder={knowledgeBaseId ? "输入问题..." : "请先选择或创建知识库"}
        className="input composer-input w-full shadow-sm"
        rows={1}
        disabled={!knowledgeBaseId}
      />
      <div className="composer-mode-row">
        <ChatScopePicker
          options={scopeOptions}
          value={chatScope}
          webSearchEnabled={webSearchEnabled}
          webSearchProvider={webSearchProvider}
          tavilyConfigured={Boolean(webSearchConfig?.tavily_configured)}
          canConfigureWebSearch={canConfigureWebSearch}
          webSearchNotice={webSearchNotice}
          onChange={onScopeChange}
          onWebSearchChange={onWebSearchChange}
          onWebSearchProviderChange={onWebSearchProviderChange}
          onConfigureTavily={onConfigureTavily}
          disabled={!knowledgeBaseId}
        />
        <button
          onClick={isGenerating ? onStopGenerating : onSend}
          disabled={!canSend && !isGenerating}
          className={`composer-send-button ${
            canSend || isGenerating ? "active" : "disabled"
          } ${isGenerating ? "generating" : ""}`}
          title={isGenerating ? "停止生成" : "发送"}
          aria-label={isGenerating ? "停止生成" : "发送"}
          type="button"
        >
          {isGenerating ? (
            <svg
              className="send-stop-icon"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <rect x="6" y="6" width="12" height="12" rx="2.4" />
            </svg>
          ) : (
            <>
              <svg
                className="send-arrow-icon"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.35}
                  d="M12 19V5m0 0-6 6m6-6 6 6"
                />
              </svg>
              发送
            </>
          )}
        </button>
      </div>
    </div>
  );
}
