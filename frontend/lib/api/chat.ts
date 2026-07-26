import { request } from "./client";
import type {
  LLMApiSource,
  LLMConfigResponse,
  LLMHealthResponse,
  LLMProvider,
  WebSearchConfigResponse,
  WebSearchProvider,
} from "./chatTypes";

export const chatApi = {
  getModelConfig: () => request<LLMConfigResponse>("/chat/llm/config"),

  getWebSearchConfig: () =>
    request<WebSearchConfigResponse>("/chat/web-search/config"),

  saveWebSearchConfig: (data: {
    provider: WebSearchProvider;
    tavily_api_key?: string;
    fallback_html?: boolean;
    tavily_search_depth?: "basic" | "advanced" | string;
  }) =>
    request<WebSearchConfigResponse>("/chat/web-search/config", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  setModelProvider: (provider: LLMProvider) =>
    request<{ ok: boolean; current_provider: string; model: string }>(
      "/chat/llm/config",
      {
        method: "POST",
        body: JSON.stringify({ provider }),
      },
    ),

  setModelSource: (apiSource: LLMApiSource) =>
    request<LLMConfigResponse>("/chat/llm/source", {
      method: "POST",
      body: JSON.stringify({ api_source: apiSource }),
    }),

  saveModelProviderConfig: (data: {
    provider: string;
    api_key?: string;
    base_url?: string;
    model?: string;
    thinking_mode: "off" | "standard" | "custom";
    thinking_config?: Record<string, unknown>;
  }) =>
    request<{
      ok: boolean;
      current_provider: string;
      model: string;
      provider_label: string;
      thinking_config: Record<string, unknown>;
      thinking_template: Record<string, unknown>;
      verified: boolean;
      latency_ms: number;
    }>("/chat/llm/provider-config", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  health: () => request<LLMHealthResponse>("/chat/health/llm"),
};
