"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  knowledgeBaseApi,
  type KnowledgeBaseChatRequest,
  type WebSearchProvider,
} from "@/lib/api";
import type { ChatScopeSelection } from "@/lib/chatScope";
import { toScopePayload } from "@/lib/chatScope";
import { parseChatStream } from "@/lib/chatStream";
import { copyText } from "@/lib/clipboard";
import { getLocalAuthHeaders } from "@/lib/localConnection";
import type { Message, Reaction } from "@/components/chat/types";

const CHAT_STREAM_IDLE_TIMEOUT_MS = 90_000;

interface UseChatStreamingParams {
  knowledgeBaseId?: number | null;
  chatScope: ChatScopeSelection;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  shouldFollowChatScrollRef: React.MutableRefObject<boolean>;
  onMessagesSettled?: (messages: Message[]) => void;
}

interface ThinkingExtraction {
  answer: string;
  thinking?: string;
}

function extractThinkingFromContent(content: string): ThinkingExtraction {
  const text = content || "";
  const thinkTagMatch = text.match(/<think>([\s\S]*?)<\/think>/i);
  if (thinkTagMatch) {
    return {
      thinking: thinkTagMatch[1].trim(),
      answer: text.replace(thinkTagMatch[0], "").trim(),
    };
  }

  const markdownMatch = text.match(
    /(?:^|\n)\s*(?:思考过程|思考|推理过程)[:：]\s*([\s\S]*?)(?:\n\s*(?:最终回答|回答|答案)[:：]\s*([\s\S]*))?$/i,
  );
  if (markdownMatch && markdownMatch[1]) {
    return {
      thinking: markdownMatch[1].trim(),
      answer: (markdownMatch[2] || text.slice(0, markdownMatch.index)).trim(),
    };
  }

  return { answer: text.trim() };
}

export function useChatStreaming({
  knowledgeBaseId,
  chatScope,
  webSearchEnabled,
  webSearchProvider,
  shouldFollowChatScrollRef,
  onMessagesSettled,
}: UseChatStreamingParams) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [regeneratingMessageId, setRegeneratingMessageId] = useState<
    string | null
  >(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingQuestion, setEditingQuestion] = useState("");
  const [reactionMap, setReactionMap] = useState<Record<string, Reaction>>({});
  const streamAbortRef = useRef<AbortController | null>(null);
  const notifySettledRef = useRef(false);

  useEffect(() => {
    if (!notifySettledRef.current) return;
    notifySettledRef.current = false;
    onMessagesSettled?.(messages);
  }, [messages, onMessagesSettled]);

  const fetchAssistantAnswer = async (q: string, assistantId: string) => {
    const abortController = new AbortController();
    streamAbortRef.current = abortController;
    const thinkingStartedAt = Date.now();
    setMessages((prev) =>
      prev.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              thinking: "",
              thinkingActive: true,
              thinkingStartedAt,
              thinkingDurationMs: undefined,
              webSearchActive: false,
              webSearchProgress: undefined,
            }
          : message,
      ),
    );
    const scopedPayload: KnowledgeBaseChatRequest = {
      question: q,
      k: 5,
      web_search: webSearchEnabled,
      web_search_provider: webSearchProvider,
      ...toScopePayload(chatScope),
    };
    let streamTimedOut = false;
    let streamBuffer = "";
    let streamIdleTimer: number | null = null;
    let didSettle = false;
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
      if (!knowledgeBaseId) return;
      const streamUrl = knowledgeBaseApi.chatStreamUrl(knowledgeBaseId);
      const response = await fetch(streamUrl, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...getLocalAuthHeaders(),
        },
        signal: abortController.signal,
        body: JSON.stringify(scopedPayload),
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
            const parsed = parseChatStream(streamBuffer);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: parsed.answer,
                      thinking: parsed.thinking || m.thinking,
                      webSearchActive:
                        parsed.webSearchProgress !== undefined
                          ? Boolean(parsed.webSearchProgress)
                          : m.webSearchActive,
                      webSearchProgress:
                        parsed.webSearchProgress !== undefined
                          ? parsed.webSearchProgress || undefined
                          : m.webSearchProgress,
                      sources: parsed.complete ? parsed.sources : m.sources,
                      webSearch: parsed.webSearch || m.webSearch,
                    }
                  : m,
              ),
            );
          }
        }
      }

      const parsed = parseChatStream(streamBuffer);
      const extracted = extractThinkingFromContent(parsed.answer);
      const finalThinking = (
        parsed.thinking ||
        extracted.thinking ||
        ""
      ).trim();
      const finalAnswer = extracted.answer;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: finalAnswer,
                thinking: finalThinking || undefined,
                webSearchActive: false,
                webSearchProgress: undefined,
                sources: parsed.sources,
                webSearch: parsed.webSearch,
              }
            : m,
        ),
      );
      didSettle = true;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        if (!streamTimedOut) {
          return;
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
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: finalAnswer,
                    thinking: finalThinking || m.thinking,
                    webSearchActive:
                      parsed.webSearchProgress !== undefined
                        ? Boolean(parsed.webSearchProgress)
                        : m.webSearchActive,
                    webSearchProgress:
                      parsed.webSearchProgress !== undefined
                        ? parsed.webSearchProgress || undefined
                        : m.webSearchProgress,
                    sources: parsed.complete ? parsed.sources : m.sources,
                    webSearch: parsed.webSearch || m.webSearch,
                  }
                : m,
            ),
          );
          didSettle = true;
          return;
        }
      }
      try {
        if (!knowledgeBaseId) return;
        const res = await knowledgeBaseApi.chat(knowledgeBaseId, scopedPayload);
        const extracted = extractThinkingFromContent(res.answer || "");
        const finalThinking = (res.thinking || extracted.thinking || "").trim();
        const finalAnswer = res.thinking
          ? (res.answer || "").trim() ||
            (finalThinking ? "（已生成思考过程，展开查看）" : "")
          : extracted.answer;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: finalAnswer,
                  thinking: finalThinking || undefined,
                  webSearchActive: false,
                  webSearchProgress: undefined,
                  sources: res.sources,
                  webSearch: res.web_search,
                }
              : m,
          ),
        );
        didSettle = true;
      } catch (fallbackError) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `错误: ${
                    fallbackError instanceof Error
                      ? fallbackError.message
                      : "请求失败"
                  }`,
                  webSearchActive: false,
                  webSearchProgress: undefined,
                }
              : m,
          ),
        );
        didSettle = true;
      }
    } finally {
      if (streamIdleTimer !== null) {
        window.clearTimeout(streamIdleTimer);
      }
      const thinkingDurationMs = Date.now() - thinkingStartedAt;
      if (didSettle) {
        notifySettledRef.current = true;
      }
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                thinkingActive: false,
                thinkingDurationMs,
                webSearchActive: false,
                webSearchProgress: undefined,
              }
            : message,
        ),
      );
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
    }
  };

  const stopGenerating = useCallback(() => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    setLoading(false);
    setRegeneratingMessageId(null);
  }, []);

  const resetChat = useCallback(() => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    setLoading(false);
    setRegeneratingMessageId(null);
    setMessages([]);
  }, []);

  const handleCopyMessage = async (messageId: string, content: string) => {
    try {
      await copyText(content);
      setCopiedMessageId(messageId);
      window.setTimeout(() => {
        setCopiedMessageId((current) =>
          current === messageId ? null : current,
        );
      }, 1500);
    } catch {
      setCopiedMessageId(null);
    }
  };

  const handleReaction = (
    messageId: string,
    reaction: Exclude<Reaction, null>,
  ) => {
    setReactionMap((prev) => ({
      ...prev,
      [messageId]: prev[messageId] === reaction ? null : reaction,
    }));
  };

  const handleEditQuestion = (messageId: string, question: string) => {
    stopGenerating();
    setEditingMessageId(messageId);
    setEditingQuestion(question);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setEditingQuestion("");
  };

  const handleSubmitEditedQuestion = async (messageId: string) => {
    const q = editingQuestion.trim();
    if (!q || loading || !!regeneratingMessageId) return;

    const assistantId = (Date.now() + 1).toString();
    setEditingMessageId(null);
    setEditingQuestion("");
    setLoading(true);

    setMessages((prev) => {
      const idx = prev.findIndex(
        (m) => m.id === messageId && m.role === "user",
      );
      if (idx === -1) return prev;
      const editedUserMessage: Message = { ...prev[idx], content: q };
      return [
        ...prev.slice(0, idx),
        editedUserMessage,
        { id: assistantId, role: "assistant", content: "", sources: [] },
      ];
    });

    try {
      await fetchAssistantAnswer(q, assistantId);
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async (assistantId: string, question: string) => {
    if (!question || loading || !!regeneratingMessageId) return;
    setRegeneratingMessageId(assistantId);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              content: "",
              thinking: undefined,
              thinkingActive: false,
              thinkingStartedAt: undefined,
              thinkingDurationMs: undefined,
              webSearchActive: false,
              webSearchProgress: undefined,
              sources: [],
              webSearch: undefined,
            }
          : m,
      ),
    );
    try {
      await fetchAssistantAnswer(question, assistantId);
    } finally {
      setRegeneratingMessageId(null);
    }
  };

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || loading) return;
    const userId = Date.now().toString();
    const assistantId = (Date.now() + 1).toString();
    shouldFollowChatScrollRef.current = true;
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: "", sources: [] },
    ]);
    setLoading(true);

    try {
      await fetchAssistantAnswer(question, assistantId);
    } finally {
      setLoading(false);
    }
  };

  return {
    messages,
    loading,
    copiedMessageId,
    regeneratingMessageId,
    editingMessageId,
    editingQuestion,
    reactionMap,
    setMessages,
    setEditingQuestion,
    resetChat,
    stopGenerating,
    handleCopyMessage,
    handleReaction,
    handleEditQuestion,
    handleCancelEdit,
    handleSubmitEditedQuestion,
    handleRegenerate,
    send,
  };
}
