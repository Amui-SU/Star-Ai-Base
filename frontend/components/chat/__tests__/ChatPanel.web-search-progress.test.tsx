import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
  cleanupChatPanelTest,
  createDeferred,
} from "@/components/chat/chatPanelTestUtils";

import { mockBasicChatPanelLoad } from "./chatPanelWebSearchHelpers";

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

describe("ChatPanel web search live progress", () => {
  it("renders web search progress as a live status outside thinking text", async () => {
    mockBasicChatPanelLoad();
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
});
