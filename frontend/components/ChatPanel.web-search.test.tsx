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
  createDeferred,
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

  it("labels knowledge and web sources in assistant references", async () => {
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
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        body: null,
      }),
    );
    vi.mocked(knowledgeBaseApi.chat).mockResolvedValue({
      answer: "answer",
      sources: [
        {
          type: "knowledge",
          bvid: "BV1",
          title: "知识库资料",
          url: "https://www.bilibili.com/video/BV1",
        },
        {
          type: "web",
          title: "外部网页",
          url: "https://example.com",
        },
      ],
    });

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.type(screen.getByRole("textbox"), "sources");
    await user.click(container.querySelector(".composer-send-button")!);
    await user.click(await screen.findByText("参考链接（2）"));

    expect(screen.getByText("知识库")).toBeVisible();
    expect(screen.getByText("网页")).toBeVisible();
    expect(screen.getByText("知识库资料")).toBeVisible();
    expect(screen.getByText("外部网页")).toBeVisible();
  });

  it("shows web sources from the streaming metadata in assistant references", async () => {
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

    const encoder = new TextEncoder();
    const streamText =
      'stream answer\n[[WEB_SEARCH_JSON]]{"status":"success","message":"已使用联网搜索","result_count":1}\n[[SOURCES_JSON]][{"type":"web","title":"Streaming Web Source","url":"https://example.com/stream"}]';
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
                  value: encoder.encode(streamText),
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

    await user.type(screen.getByRole("textbox"), "stream sources");
    await user.click(container.querySelector(".composer-send-button")!);
    await user.click(await screen.findByText("参考链接（1）"));

    expect(screen.getByText("网页")).toBeVisible();
    expect(screen.getByText("Streaming Web Source")).toBeVisible();
    expect(screen.getByText("已使用联网搜索")).toBeVisible();
  });

  it("renders web search progress as a live status outside thinking text", async () => {
    mockChatPanelDependencies();
    const encoder = new TextEncoder();
    const pendingReads: Array<
      ReturnType<typeof createDeferred<ReadableStreamReadResult<Uint8Array>>>
    > = [];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn(() => {
              const pending =
                createDeferred<ReadableStreamReadResult<Uint8Array>>();
              pendingReads.push(pending);
              return pending.promise;
            }),
          }),
        },
      }),
    );

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.type(screen.getByRole("textbox"), "search progress");
    await user.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(pendingReads).toHaveLength(1);
    });

    await act(async () => {
      pendingReads[0].resolve({
        done: false,
        value: encoder.encode(
          '[[WEB_SEARCH_PROGRESS]]"正在联网搜索外部资料"\n',
        ),
      });
      await Promise.resolve();
    });

    expect(screen.getByRole("status")).toHaveTextContent(
      "正在联网搜索外部资料",
    );
    expect(
      screen.getByRole("status").querySelector(".web-search-live-text"),
    ).not.toBeNull();
    expect(
      container.querySelector(".thinking-process-content")?.textContent ?? "",
    ).not.toContain("正在联网搜索外部资料");

    await act(async () => {
      pendingReads[1].resolve({
        done: false,
        value: encoder.encode(
          '[[WEB_SEARCH_PROGRESS]]""\nstream answer\n[[SOURCES_JSON]][]',
        ),
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });
    expect(screen.getByText("stream answer")).toBeVisible();
  });

  it("clears previous references immediately when regenerating an answer", async () => {
    mockChatPanelDependencies();
    const encoder = new TextEncoder();
    const secondRead = createDeferred<ReadableStreamReadResult<Uint8Array>>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
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
                  value: encoder.encode(
                    'first answer\n[[WEB_SEARCH_JSON]]{"status":"success","message":"已使用联网搜索","result_count":1}\n[[SOURCES_JSON]][{"type":"web","title":"Old Web","url":"https://example.com/old"}]',
                  ),
                });
              }),
            };
          },
        },
      })
      .mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn(() => secondRead.promise),
          }),
        },
      });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.type(screen.getByRole("textbox"), "original question");
    await user.click(container.querySelector(".composer-send-button")!);

    expect(await screen.findByText("参考链接（1）")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "重新生成" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText(/参考链接/)).not.toBeInTheDocument();

    secondRead.resolve({ done: true, value: undefined });
  });

  it("shows web search fallback status returned by the chat response", async () => {
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
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        body: null,
      }),
    );
    vi.mocked(knowledgeBaseApi.chat).mockResolvedValue({
      answer: "answer",
      sources: [
        {
          type: "web",
          title: "搜索结果标题",
          url: "https://example.com/search-result",
        },
      ],
      web_search: {
        status: "failed",
        message: "联网搜索失败，已仅参考知识库",
        result_count: 0,
        queries: ["failed query"],
        results: [
          {
            title: "搜索结果标题",
            url: "https://example.com/search-result",
            snippet: "搜索结果摘要",
          },
        ],
      },
    });

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.type(screen.getByRole("textbox"), "sources");
    await user.click(container.querySelector(".composer-send-button")!);

    expect(await screen.findByText("参考链接（1）")).toBeVisible();
    const foldedFailureStatus =
      screen.queryByText("联网搜索失败，已仅参考知识库");
    if (foldedFailureStatus) {
      expect(foldedFailureStatus).not.toBeVisible();
    }

    await user.click(screen.getByText("参考链接（1）"));

    expect(screen.getByText("联网搜索失败，已仅参考知识库")).toBeVisible();
    expect(screen.getByText("搜索结果标题")).toBeInTheDocument();
    expect(screen.queryByText("搜索结果")).not.toBeInTheDocument();
    expect(screen.queryByText("搜索结果摘要")).not.toBeInTheDocument();
  });

  it("shows attempted queries when web search returns no results", async () => {
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
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        body: null,
      }),
    );
    vi.mocked(knowledgeBaseApi.chat).mockResolvedValue({
      answer: "answer",
      sources: [],
      web_search: {
        status: "no_results",
        message: "联网搜索未找到可用结果，已仅参考知识库",
        result_count: 0,
        queries: ["DeepSeek V4Pro web_search 返回空结果"],
        results: [],
        errors: [
          {
            source: "duckduckgo",
            query: "DeepSeek V4Pro web_search 返回空结果",
            message: "proxy connection refused（未配置 HTTP_PROXY）",
          },
        ],
      },
    });

    const user = userEvent.setup();
    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );

    await user.type(screen.getByRole("textbox"), "sources");
    await user.click(container.querySelector(".composer-send-button")!);

    expect(await screen.findByText("搜索状态")).toBeVisible();
    expect(screen.queryByText("参考链接（0）")).not.toBeInTheDocument();
    const foldedNoResultsStatus = screen.queryByText(
      "联网搜索未找到可用结果，已仅参考知识库",
    );
    if (foldedNoResultsStatus) {
      expect(foldedNoResultsStatus).not.toBeVisible();
    }
    const foldedQueries = screen.queryByText("尝试查询");
    if (foldedQueries) {
      expect(foldedQueries).not.toBeVisible();
    }

    await user.click(screen.getByText("搜索状态"));

    expect(
      screen.getByText("联网搜索未找到可用结果，已仅参考知识库"),
    ).toBeVisible();
    expect(screen.getByText("尝试查询")).toBeVisible();
    expect(
      screen.getByText("DeepSeek V4Pro web_search 返回空结果"),
    ).toBeVisible();
    expect(screen.getByText("诊断信息")).toBeVisible();
    expect(
      screen.getByText("proxy connection refused（未配置 HTTP_PROXY）"),
    ).toBeVisible();
  });
});
