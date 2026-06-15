import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import { chatApi, knowledgeBaseApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      getModelConfig: vi.fn(),
      health: vi.fn(),
      setModelProvider: vi.fn(),
    },
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      stats: vi.fn(),
      getScopeOptions: vi.fn(),
      chatStreamUrl: vi.fn(),
      chat: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("ChatPanel", () => {
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
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
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
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
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
});
