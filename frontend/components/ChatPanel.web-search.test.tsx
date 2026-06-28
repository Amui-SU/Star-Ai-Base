import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  chatApi,
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

describe("ChatPanel web search behavior", () => {
  it("sends the web search flag when the picker toggle is enabled", async () => {
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
    vi.mocked(chatApi.getWebSearchConfig).mockResolvedValue({
      provider: "auto",
      tavily_configured: false,
      fallback_html: true,
      tavily_search_depth: "basic",
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

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.keyboard("{Escape}");
    await user.type(screen.getByRole("textbox"), "latest news");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      question: "latest news",
      web_search: true,
      web_search_provider: "auto",
    });
  });

  it("resets the web search provider to auto when enabling search from the picker", async () => {
    mockChatPanelDependencies();
    vi.mocked(chatApi.getWebSearchConfig).mockResolvedValue({
      provider: "tavily",
      tavily_configured: true,
      fallback_html: true,
      tavily_search_depth: "basic",
    });
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

    await waitFor(() => {
      expect(chatApi.getWebSearchConfig).toHaveBeenCalled();
    });
    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.type(screen.getByRole("textbox"), "latest news");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      question: "latest news",
      web_search: true,
      web_search_provider: "auto",
    });
  });

  it("opens Tavily config from web search provider choice and sends Tavily after saving", async () => {
    mockChatPanelDependencies();
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

    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: /^提问范围/ }));
    await user.click(screen.getByRole("button", { name: "Tavily" }));
    expect(screen.getByText("配置联网搜索")).toBeVisible();

    await user.type(screen.getByLabelText("Tavily API Key"), "tvly-test");
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    await waitFor(() => {
      expect(chatApi.saveWebSearchConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "tavily",
          tavily_api_key: "tvly-test",
        }),
      );
    });

    await user.type(
      screen.getByPlaceholderText("输入问题..."),
      "search with tavily",
    );
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(requestInit.body))).toMatchObject({
      question: "search with tavily",
      web_search: true,
      web_search_provider: "tavily",
    });
  });

  it("shows the web search notice only on the scope chip and then restores the scope text", async () => {
    vi.useFakeTimers();
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

    render(<ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />);

    fireEvent.click(screen.getByRole("button", { name: /^提问范围/ }));
    fireEvent.click(screen.getByRole("button", { name: "联网搜索" }));

    expect(screen.getAllByText("联网搜索已开启")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /^提问范围/ })).toHaveTextContent(
      "联网搜索已开启",
    );

    act(() => {
      vi.advanceTimersByTime(2200);
    });

    expect(screen.queryByText("联网搜索已开启")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^提问范围/ })).toHaveTextContent(
      "整个知识库",
    );
  });
});
