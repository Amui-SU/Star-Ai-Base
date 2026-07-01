import { vi } from "vitest";

import {
  chatApi,
  knowledgeBaseApi,
} from "@/components/chat/chatPanelTestUtils";

export function mockBasicChatPanelLoad() {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(chatApi.getModelConfig).mockResolvedValue({
    current_provider: "dashscope",
    providers: [
      {
        provider: "dashscope",
        label: "DashScope",
        enabled: true,
        model: "qwen-plus",
        thinking_config: {},
        thinking_template: {},
      },
    ],
  });
  vi.mocked(chatApi.health).mockResolvedValue({
    status: "up",
    message: "ok",
    latency_ms: 10,
    model: "qwen-plus",
    provider: "dashscope",
  });
  vi.mocked(knowledgeBaseApi.stats).mockResolvedValue({
    knowledge_base_id: 1,
    workspace_id: 1,
    total_videos: 0,
    folders: [],
    scoped: true,
  });
  vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
    folders: [],
  });
  vi.mocked(knowledgeBaseApi.chatStreamUrl).mockReturnValue(
    "http://localhost:8000/knowledge-bases/1/chat/stream",
  );
}

export function mockFailedStreamingFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      body: null,
    }),
  );
}
