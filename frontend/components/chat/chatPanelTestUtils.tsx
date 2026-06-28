import { cleanup } from "@testing-library/react";
import { vi } from "vitest";

import { chatApi, chatHistoryApi, knowledgeBaseApi } from "@/lib/api";

export { chatApi, chatHistoryApi, knowledgeBaseApi };

export function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

export function mockChatPanelDependencies() {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(chatApi.getModelConfig).mockResolvedValue({
    current_provider: "deepseek",
    providers: [
      {
        provider: "deepseek",
        label: "DeepSeek",
        enabled: true,
        model: "deepseek-v4-pro",
        thinking_config: { thinking: { type: "enabled" } },
        thinking_template: { thinking: { type: "enabled" } },
      },
    ],
  });
  vi.mocked(chatApi.health).mockResolvedValue({
    status: "up",
    message: "ok",
    latency_ms: 10,
    model: "deepseek-v4-pro",
    provider: "deepseek",
  });
  vi.mocked(chatApi.getWebSearchConfig).mockResolvedValue({
    provider: "auto",
    tavily_configured: false,
    fallback_html: true,
    tavily_search_depth: "basic",
  });
  vi.mocked(chatApi.saveWebSearchConfig).mockResolvedValue({
    provider: "tavily",
    tavily_configured: true,
    fallback_html: true,
    tavily_search_depth: "basic",
  });
  vi.mocked(chatApi.setModelSource).mockResolvedValue({
    current_provider: "deepseek",
    current_api_source: "personal",
    providers: [
      {
        provider: "deepseek",
        label: "DeepSeek",
        enabled: true,
        official_enabled: true,
        personal_enabled: true,
        model: "deepseek-v4-pro",
        thinking_config: { thinking: { type: "enabled" } },
        thinking_template: { thinking: { type: "enabled" } },
      },
    ],
  });
  vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
    knowledge_base_id: 1,
    workspace_id: 1,
    total_videos: 1,
    folders: [],
    scoped: true,
  });
  vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
    folders: [],
  });
  vi.mocked(knowledgeBaseApi.chatStreamUrl).mockReturnValue(
    "http://localhost:8000/knowledge-bases/1/chat/stream",
  );
  vi.mocked(chatHistoryApi.list).mockResolvedValue({ items: [] });
  vi.mocked(chatHistoryApi.create).mockImplementation(async (data) => ({
    id: 101,
    user_id: 1,
    workspace_id: data.workspace_id ?? null,
    knowledge_base_id: data.knowledge_base_id ?? null,
    title: data.title || data.messages[0]?.content || "新对话",
    scope: data.scope ?? null,
    web_search: data.web_search,
    web_search_provider: data.web_search_provider,
    message_count: data.messages.length,
    created_at: "2026-06-26T00:00:00Z",
    updated_at: "2026-06-26T00:00:00Z",
    messages: data.messages.map((message, index) => ({
      id: index + 1,
      sequence: index,
      created_at: "2026-06-26T00:00:00Z",
      ...message,
    })),
  }));
  vi.mocked(chatHistoryApi.update).mockImplementation(async (id, data) => ({
    id,
    user_id: 1,
    workspace_id: data.workspace_id ?? null,
    knowledge_base_id: data.knowledge_base_id ?? null,
    title: data.title || data.messages[0]?.content || "新对话",
    scope: data.scope ?? null,
    web_search: data.web_search,
    web_search_provider: data.web_search_provider,
    message_count: data.messages.length,
    created_at: "2026-06-26T00:00:00Z",
    updated_at: "2026-06-26T00:00:00Z",
    messages: data.messages.map((message, index) => ({
      id: index + 1,
      sequence: index,
      created_at: "2026-06-26T00:00:00Z",
      ...message,
    })),
  }));
}

export function cleanupChatPanelTest() {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
}
