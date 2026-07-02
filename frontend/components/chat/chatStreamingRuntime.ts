"use client";

import {
  knowledgeBaseApi,
  type ChatResponse,
  type KnowledgeBaseChatRequest,
} from "@/lib/api";
import { parseChatStream, type ParsedChatStream } from "@/lib/chatStream";
import { getLocalAuthHeaders } from "@/lib/localConnection";
import { extractThinkingFromContent } from "@/components/chat/chatStreamingState";

export const CHAT_STREAM_IDLE_TIMEOUT_MS = 90_000;

export type ChatStreamingRuntimeResult =
  | { status: "streamed"; parsed: ParsedChatStream }
  | {
      status: "partial";
      parsed: ParsedChatStream;
      content: string;
      thinking?: string;
    }
  | { status: "fallback"; response: ChatResponse }
  | { status: "aborted" }
  | { status: "error"; message: string };

interface StreamKnowledgeBaseAnswerParams {
  knowledgeBaseId: number;
  payload: KnowledgeBaseChatRequest;
  onAbortController?: (abortController: AbortController) => void;
  onParsedStream: (parsed: ParsedChatStream) => void;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败";
}

export function streamKnowledgeBaseAnswer({
  knowledgeBaseId,
  payload,
  onAbortController,
  onParsedStream,
}: StreamKnowledgeBaseAnswerParams): Promise<ChatStreamingRuntimeResult> {
  const abortController = new AbortController();
  onAbortController?.(abortController);
  return runKnowledgeBaseAnswerStream({
    knowledgeBaseId,
    payload,
    abortController,
    onParsedStream,
  });
}

async function runKnowledgeBaseAnswerStream({
  knowledgeBaseId,
  payload,
  abortController,
  onParsedStream,
}: StreamKnowledgeBaseAnswerParams & {
  abortController: AbortController;
}): Promise<ChatStreamingRuntimeResult> {
  let streamTimedOut = false;
  let streamBuffer = "";
  let streamIdleTimer: number | null = null;

  const resetStreamIdleTimer = () => {
    if (streamIdleTimer !== null) {
      window.clearTimeout(streamIdleTimer);
    }
    streamIdleTimer = window.setTimeout(() => {
      streamTimedOut = true;
      abortController.abort();
    }, CHAT_STREAM_IDLE_TIMEOUT_MS);
  };

  resetStreamIdleTimer();
  try {
    const streamUrl = knowledgeBaseApi.chatStreamUrl(knowledgeBaseId);
    const response = await fetch(streamUrl, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...getLocalAuthHeaders(),
      },
      signal: abortController.signal,
      body: JSON.stringify(payload),
    });

    if (!response.ok || !response.body) {
      throw new Error("流式接口不可用");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      if (value) {
        resetStreamIdleTimer();
        const chunk = decoder.decode(value, { stream: !done });
        if (chunk) {
          streamBuffer += chunk;
          onParsedStream(parseChatStream(streamBuffer));
        }
      }
    }

    return {
      status: "streamed",
      parsed: parseChatStream(streamBuffer),
    };
  } catch (error) {
    if (isAbortError(error)) {
      if (!streamTimedOut) {
        return { status: "aborted" };
      }
      const parsed = parseChatStream(streamBuffer);
      const extracted = extractThinkingFromContent(parsed.answer);
      const finalThinking = (
        parsed.thinking ||
        extracted.thinking ||
        ""
      ).trim();
      const finalAnswer = extracted.answer;
      if (finalAnswer.trim() || finalThinking) {
        return {
          status: "partial",
          parsed,
          content: finalAnswer,
          thinking: finalThinking || undefined,
        };
      }
    }

    try {
      const response = await knowledgeBaseApi.chat(knowledgeBaseId, payload);
      return { status: "fallback", response };
    } catch (fallbackError) {
      return { status: "error", message: errorMessage(fallbackError) };
    }
  } finally {
    if (streamIdleTimer !== null) {
      window.clearTimeout(streamIdleTimer);
    }
  }
}
