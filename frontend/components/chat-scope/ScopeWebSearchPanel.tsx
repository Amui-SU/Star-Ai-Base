"use client";

import type { WebSearchProvider } from "@/lib/api";

const WEB_SEARCH_PROVIDERS: ReadonlyArray<
  readonly [WebSearchProvider, string]
> = [
  ["auto", "自动"],
  ["tavily", "Tavily"],
  ["html", "内置"],
];

interface ScopeWebSearchPanelProps {
  summary: string;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  tavilyConfigured: boolean;
  canConfigureWebSearch: boolean;
  onToggleWebSearch: () => void;
  onWebSearchProviderChange: (provider: WebSearchProvider) => void;
  onConfigureTavily: () => void;
}

export default function ScopeWebSearchPanel({
  summary,
  webSearchEnabled,
  webSearchProvider,
  tavilyConfigured,
  canConfigureWebSearch,
  onToggleWebSearch,
  onWebSearchProviderChange,
  onConfigureTavily,
}: ScopeWebSearchPanelProps) {
  return (
    <>
      <div className="scope-picker-head">
        <div>
          <div className="scope-picker-title">提问范围</div>
          <div className="scope-picker-subtitle">{summary}</div>
        </div>
        <button
          type="button"
          className={`scope-web-search-btn ${webSearchEnabled ? "active" : ""}`}
          aria-label="联网搜索"
          aria-describedby="scope-web-search-privacy"
          aria-pressed={webSearchEnabled}
          title="开启后，模型可能向外部搜索服务发送查询并读取公开网页"
          onClick={onToggleWebSearch}
        >
          <span className="scope-web-dot" aria-hidden="true" />
          联网搜索
        </button>
        <span id="scope-web-search-privacy" className="scope-visually-hidden">
          开启后，模型可能向外部搜索服务发送查询并读取公开网页
        </span>
      </div>

      {webSearchEnabled && (
        <div className="scope-web-provider-panel">
          <div
            className="scope-web-provider-options"
            role="group"
            aria-label="联网搜索方式"
          >
            {WEB_SEARCH_PROVIDERS.map(([provider, label]) => (
              <button
                key={provider}
                type="button"
                className={`scope-web-provider-option ${
                  webSearchProvider === provider ? "active" : ""
                }`}
                aria-pressed={webSearchProvider === provider}
                disabled={
                  provider === "tavily" &&
                  !tavilyConfigured &&
                  !canConfigureWebSearch
                }
                title={
                  provider === "tavily" &&
                  !tavilyConfigured &&
                  !canConfigureWebSearch
                    ? "Tavily 需要管理员配置"
                    : undefined
                }
                onClick={() => onWebSearchProviderChange(provider)}
              >
                {label}
              </button>
            ))}
          </div>
          {!tavilyConfigured && !canConfigureWebSearch && (
            <div className="scope-web-config-note">Tavily 需要管理员配置</div>
          )}
          {webSearchProvider === "tavily" &&
            !tavilyConfigured &&
            canConfigureWebSearch && (
              <button
                type="button"
                className="scope-web-config-btn"
                onClick={onConfigureTavily}
              >
                配置 Tavily
              </button>
            )}
        </div>
      )}
    </>
  );
}
