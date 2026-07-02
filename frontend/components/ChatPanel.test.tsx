import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  chatApi,
  chatHistoryApi,
  cleanupChatPanelTest,
  knowledgeBaseApi,
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

describe("ChatPanel", () => {
  it("keeps send disabled when no knowledge base is selected", async () => {
    mockChatPanelDependencies();
    const user = userEvent.setup();
    render(<ChatPanel />);

    await screen.findByText("探索你的收藏");
    await user.click(
      screen.getByRole("button", { name: "总结收藏夹里最有价值的内容" }),
    );

    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });

  it("saves the completed streaming answer with scope and web search metadata", async () => {
    mockChatPanelDependencies();
    vi.mocked(knowledgeBaseApi.getScopeOptions).mockResolvedValue({
      folders: [
        {
          media_id: 10,
          title: "AI 收藏夹",
          video_count: 1,
          videos: [],
        },
      ],
    });
    const encoder = new TextEncoder();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => {
            let read = false;
            return {
              read: vi.fn().mockImplementation(() => {
                if (read)
                  return Promise.resolve({ done: true, value: undefined });
                read = true;
                return Promise.resolve({
                  done: false,
                  value: encoder.encode("stream answer"),
                });
              }),
            };
          },
        },
      }),
    );
    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.click(await screen.findByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("checkbox", { name: /AI 收藏夹/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.keyboard("{Escape}");
    await user.type(screen.getByRole("textbox"), "stream sources");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(chatHistoryApi.create).toHaveBeenCalled();
    });
    expect(chatHistoryApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        knowledge_base_id: 1,
        scope: { folder_ids: [10], bvids: [] },
        web_search: true,
        web_search_provider: "auto",
        messages: [
          expect.objectContaining({
            role: "user",
            content: "stream sources",
          }),
          expect.objectContaining({
            role: "assistant",
            content: "stream answer",
          }),
        ],
      }),
    );
  });

  it("marks the AI disclaimer so mobile layout can hide it without changing desktop", async () => {
    mockChatPanelDependencies();

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    expect(await screen.findByText("探索你的收藏")).toBeVisible();
    expect(screen.getByText("内容由 AI 生成，请注意甄别。")).toHaveClass(
      "composer-disclaimer",
    );
    expect(container.querySelector(".composer-disclaimer")).toBeInTheDocument();
  });

  it("includes credentials on the streaming chat request", async () => {
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

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        }),
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" isAdmin />,
    );

    await user.type(screen.getByRole("textbox"), "hello");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/knowledge-bases/1/chat/stream",
        expect.objectContaining({
          credentials: "include",
        }),
      );
    });
    expect(screen.getByText("已完成生成 · 未返回独立思考内容")).toBeVisible();
    expect(screen.queryByText("清空对话")).not.toBeInTheDocument();
  });

  it("uses one assistant message for the active thinking state", async () => {
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

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn(() => new Promise(() => {})),
          }),
        },
      }),
    );

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" isAdmin />,
    );

    await waitFor(() => {
      expect(chatApi.getModelConfig).toHaveBeenCalled();
    });
    await user.type(screen.getByRole("textbox"), "show thinking");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(container.querySelectorAll(".message.assistant")).toHaveLength(1);
    });
    expect(
      screen.getByText("正在读取知识库并等待模型返回思考内容"),
    ).toBeVisible();
  });

  it("opens video notes from knowledge source references", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatHistoryApi.get).mockResolvedValue({
      id: 42,
      user_id: 1,
      workspace_id: 1,
      knowledge_base_id: 1,
      title: "Loaded answer",
      scope: null,
      web_search: false,
      web_search_provider: "auto",
      message_count: 1,
      created_at: "2026-06-26T00:00:00Z",
      updated_at: "2026-06-26T00:00:00Z",
      messages: [
        {
          id: 1,
          sequence: 0,
          role: "assistant",
          content: "answer",
          sources: [
            {
              type: "knowledge",
              bvid: "BVNOTE123",
              title: "知识库资料",
              url: "https://www.bilibili.com/video/BVNOTE123",
            },
          ],
          created_at: "2026-06-26T00:00:00Z",
        },
      ],
    });
    const onOpenVideoNote = vi.fn();
    const user = userEvent.setup();

    render(
      <ChatPanel
        knowledgeBaseId={1}
        knowledgeBaseName="Test KB"
        conversationOpenRequest={{ id: 42, key: 1 }}
        onOpenVideoNote={onOpenVideoNote}
      />,
    );

    await user.click(await screen.findByText("参考链接（1）"));
    await user.click(
      screen.getByRole("button", { name: "打开视频笔记 知识库资料" }),
    );

    expect(onOpenVideoNote).toHaveBeenCalledWith("BVNOTE123");
  });
});
