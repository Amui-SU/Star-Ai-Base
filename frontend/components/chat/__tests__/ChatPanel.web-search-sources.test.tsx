import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  cleanupChatPanelTest,
  createDeferred,
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

describe("ChatPanel web search source references", () => {
  it("labels knowledge and web sources in assistant references", async () => {
    mockBasicChatPanelLoad();
    mockFailedStreamingFetch();
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
    mockBasicChatPanelLoad();

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

  it("clears previous references immediately when regenerating an answer", async () => {
    mockBasicChatPanelLoad();
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
});
