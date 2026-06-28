import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  chatHistoryApi,
  cleanupChatPanelTest,
  mockChatPanelDependencies,
} from "@/components/chat/chatPanelTestUtils";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
      getWebSearchConfig: vi.fn(),
      health: vi.fn(),
      saveWebSearchConfig: vi.fn(),
      setModelProvider: vi.fn(),
      setModelSource: vi.fn(),
    },
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      stats: vi.fn(),
      getScopeOptions: vi.fn(),
      chatStreamUrl: vi.fn(),
      chat: vi.fn(),
    },
    chatHistoryApi: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
  };
});

afterEach(cleanupChatPanelTest);

describe("ChatPanel history integration", () => {
  it("opens a requested conversation from the expanded history panel", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatHistoryApi.get).mockResolvedValue({
      id: 42,
      user_id: 1,
      workspace_id: 1,
      knowledge_base_id: 1,
      title: "RAG follow-up",
      scope: { folder_ids: [10], bvids: ["BV1ABC"] },
      web_search: true,
      web_search_provider: "tavily",
      message_count: 2,
      created_at: "2026-06-26T00:00:00Z",
      updated_at: "2026-06-26T01:00:00Z",
      messages: [
        {
          id: 1,
          role: "user",
          content: "Explain RAG",
          sequence: 0,
          created_at: "2026-06-26T00:00:00Z",
        },
        {
          id: 2,
          role: "assistant",
          content: "RAG combines retrieval and generation.",
          thinking: "Need concise answer",
          sources: [
            {
              type: "knowledge",
              title: "RAG intro",
              url: "https://www.bilibili.com/video/BV1ABC",
              bvid: "BV1ABC",
            },
          ],
          web_search: { status: "success", message: "used web" },
          sequence: 1,
          created_at: "2026-06-26T00:00:01Z",
        },
      ],
    });

    render(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        conversationOpenRequest={{ id: 42, key: 1 }}
      />,
    );

    await waitFor(() => {
      expect(chatHistoryApi.get).toHaveBeenCalledWith(42);
    });
    expect(screen.getByText("Explain RAG")).toBeVisible();
    expect(
      screen.getByText("RAG combines retrieval and generation."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "鏈€杩戝璇?" })).toBeNull();
  });

  it("starts a new conversation from an expanded-page request without deleting saved history", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatHistoryApi.get).mockResolvedValue({
      id: 42,
      user_id: 1,
      workspace_id: 1,
      knowledge_base_id: 1,
      title: "Saved chat",
      scope: null,
      web_search: false,
      web_search_provider: "auto",
      message_count: 2,
      created_at: "2026-06-26T00:00:00Z",
      updated_at: "2026-06-26T01:00:00Z",
      messages: [
        {
          id: 1,
          role: "user",
          content: "old question",
          sequence: 0,
          created_at: "2026-06-26T00:00:00Z",
        },
        {
          id: 2,
          role: "assistant",
          content: "old answer",
          sequence: 1,
          created_at: "2026-06-26T00:00:01Z",
        },
      ],
    });

    const { rerender } = render(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        conversationOpenRequest={{ id: 42, key: 1 }}
        newConversationRequestKey={0}
      />,
    );
    expect(await screen.findByText("old answer")).toBeVisible();

    rerender(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        conversationOpenRequest={{ id: 42, key: 1 }}
        newConversationRequestKey={1}
      />,
    );

    expect(screen.queryByText("old answer")).not.toBeInTheDocument();
    expect(chatHistoryApi.delete).not.toHaveBeenCalled();
  });
});
