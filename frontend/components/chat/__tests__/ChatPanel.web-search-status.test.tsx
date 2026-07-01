import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  cleanupChatPanelTest,
  knowledgeBaseApi,
} from "@/components/chat/chatPanelTestUtils";

import {
  mockBasicChatPanelLoad,
  mockFailedStreamingFetch,
} from "./chatPanelWebSearchHelpers";

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

describe("ChatPanel web search status diagnostics", () => {
  it("shows web search fallback status returned by the chat response", async () => {
    mockBasicChatPanelLoad();
    mockFailedStreamingFetch();
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
    mockBasicChatPanelLoad();
    mockFailedStreamingFetch();
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
