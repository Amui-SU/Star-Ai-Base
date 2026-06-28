import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel";
import {
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

describe("ChatPanel streaming behavior", () => {
  it("keeps a streaming response alive after the old fixed deadline when content arrived", async () => {
    vi.useFakeTimers();
    mockChatPanelDependencies();
    const encoder = new TextEncoder();
    const pendingReads: Array<
      ReturnType<typeof createDeferred<ReadableStreamReadResult<Uint8Array>>>
    > = [];
    let abortSignal: AbortSignal | undefined;

    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      abortSignal = init?.signal as AbortSignal | undefined;
      return Promise.resolve({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn(() => {
              const pending =
                createDeferred<ReadableStreamReadResult<Uint8Array>>();
              pendingReads.push(pending);
              abortSignal?.addEventListener(
                "abort",
                () => pending.reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
              return pending.promise;
            }),
          }),
        },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "slow stream" },
    });
    fireEvent.click(container.querySelector(".composer-send-button")!);

    await act(async () => {
      await Promise.resolve();
    });
    expect(pendingReads).toHaveLength(1);

    await act(async () => {
      pendingReads[0].resolve({
        done: false,
        value: encoder.encode("partial answer"),
      });
      await Promise.resolve();
    });
    expect(screen.getByText("partial answer")).toBeVisible();
    expect(pendingReads).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(abortSignal?.aborted).toBe(false);
    expect(knowledgeBaseApi.chat).not.toHaveBeenCalled();
  });

  it("uses instant autoscroll during streaming updates to avoid repeated smooth-scroll jank", async () => {
    mockChatPanelDependencies();
    const scrollMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollMock;
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

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "smooth stream" },
    });
    fireEvent.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(pendingReads).toHaveLength(1);
    });

    await act(async () => {
      pendingReads[0].resolve({
        done: false,
        value: encoder.encode("stream chunk"),
      });
      await Promise.resolve();
    });

    expect(screen.getByText("stream chunk")).toBeVisible();
    expect(scrollMock).not.toHaveBeenCalledWith(
      expect.objectContaining({ behavior: "smooth" }),
    );
  });

  it("does not force autoscroll while the user reads earlier content during streaming", async () => {
    mockChatPanelDependencies();
    const scrollMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollMock;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
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

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "let me read while streaming" },
    });
    fireEvent.click(container.querySelector(".composer-send-button")!);

    await waitFor(() => {
      expect(pendingReads).toHaveLength(1);
    });

    const scrollContainer = container.querySelector(
      ".chat-scroll",
    ) as HTMLDivElement;
    Object.defineProperties(scrollContainer, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, value: 1200 },
      scrollTop: { configurable: true, value: 240 },
    });
    fireEvent.scroll(scrollContainer);
    scrollMock.mockClear();

    await act(async () => {
      pendingReads[0].resolve({
        done: false,
        value: encoder.encode("stream chunk after user scrolled up"),
      });
      await Promise.resolve();
    });

    expect(
      screen.getByText("stream chunk after user scrolled up"),
    ).toBeVisible();
    expect(scrollMock).not.toHaveBeenCalled();
  });

  it("does not call the non-stream fallback after idle timeout when partial content exists", async () => {
    vi.useFakeTimers();
    mockChatPanelDependencies();
    vi.mocked(knowledgeBaseApi.chat).mockResolvedValue({
      answer: "fallback answer",
      sources: [],
    });
    const encoder = new TextEncoder();
    const pendingReads: Array<
      ReturnType<typeof createDeferred<ReadableStreamReadResult<Uint8Array>>>
    > = [];
    let abortSignal: AbortSignal | undefined;

    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      abortSignal = init?.signal as AbortSignal | undefined;
      return Promise.resolve({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn(() => {
              const pending =
                createDeferred<ReadableStreamReadResult<Uint8Array>>();
              pendingReads.push(pending);
              abortSignal?.addEventListener(
                "abort",
                () => pending.reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
              return pending.promise;
            }),
          }),
        },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <ChatPanel knowledgeBaseId={1} knowledgeBaseName="Test KB" />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "slow stream" },
    });
    fireEvent.click(container.querySelector(".composer-send-button")!);

    await act(async () => {
      await Promise.resolve();
    });
    expect(pendingReads).toHaveLength(1);

    await act(async () => {
      pendingReads[0].resolve({
        done: false,
        value: encoder.encode("partial answer"),
      });
      await Promise.resolve();
    });
    expect(screen.getByText("partial answer")).toBeVisible();
    expect(pendingReads).toHaveLength(2);

    await act(async () => {
      vi.advanceTimersByTime(91_000);
      await Promise.resolve();
    });

    expect(abortSignal?.aborted).toBe(true);
    expect(knowledgeBaseApi.chat).not.toHaveBeenCalled();
    expect(screen.getByText(/partial answer/)).toBeVisible();
  });
});
