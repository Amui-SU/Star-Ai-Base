import { describe, expect, it, vi } from "vitest";

import { streamKnowledgeBaseAnswer } from "@/components/chat/chatStreamingRuntime";
import { knowledgeBaseApi } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    knowledgeBaseApi: {
      ...actual.knowledgeBaseApi,
      chatStreamUrl: vi.fn(),
      chat: vi.fn(),
    },
  };
});

describe("chatStreamingRuntime", () => {
  it("streams parsed chunks and returns the final parsed answer", async () => {
    const encoder = new TextEncoder();
    vi.mocked(knowledgeBaseApi.chatStreamUrl).mockReturnValue(
      "http://api.test/knowledge-bases/7/chat/stream",
    );
    const read = vi
      .fn()
      .mockResolvedValueOnce({
        done: false,
        value: encoder.encode("hello"),
      })
      .mockResolvedValueOnce({
        done: false,
        value: encoder.encode(
          '\n[[SOURCES_JSON]][{"title":"Doc","url":"/doc"}]',
        ),
      })
      .mockResolvedValueOnce({ done: true, value: undefined });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({ read }),
        },
      }),
    );
    const onParsedStream = vi.fn();
    const onAbortController = vi.fn();

    const result = await streamKnowledgeBaseAnswer({
      knowledgeBaseId: 7,
      payload: { question: "q", k: 5 },
      onAbortController,
      onParsedStream,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/knowledge-bases/7/chat/stream",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        signal: expect.any(AbortSignal),
        body: JSON.stringify({ question: "q", k: 5 }),
      }),
    );
    expect(onAbortController).toHaveBeenCalledWith(expect.any(AbortController));
    expect(onParsedStream).toHaveBeenCalledWith(
      expect.objectContaining({ answer: "hello", complete: false }),
    );
    expect(result).toEqual({
      status: "streamed",
      parsed: expect.objectContaining({
        answer: "hello",
        complete: true,
        sources: [{ title: "Doc", url: "/doc" }],
      }),
    });
  });
});
