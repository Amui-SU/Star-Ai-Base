"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { KnowledgeBaseChatRequest, WebSearchProvider } from "@/lib/api";
import type { ChatScopeSelection } from "@/lib/chatScope";
import { toScopePayload } from "@/lib/chatScope";
import { copyText } from "@/lib/clipboard";
import type { Message, Reaction } from "@/components/chat/types";
import { streamKnowledgeBaseAnswer } from "@/components/chat/chatStreamingRuntime";
import {
  applyAssistantError,
  applyParsedStreamUpdate,
  finalizeFallbackAssistantAnswer,
  finalizeStreamedAssistantAnswer,
  resetAssistantForRegeneration,
  startAssistantStreaming,
  updateAssistantMessage,
} from "@/components/chat/chatStreamingState";

interface UseChatStreamingParams {
  knowledgeBaseId?: number | null;
  chatScope: ChatScopeSelection;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  shouldFollowChatScrollRef: React.MutableRefObject<boolean>;
  onMessagesSettled?: (messages: Message[]) => void;
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
    const thinkingStartedAt = Date.now();
    setMessages((prev) =>
      updateAssistantMessage(prev, assistantId, (message) =>
        startAssistantStreaming(message, thinkingStartedAt),
      ),
    );
    const scopedPayload: KnowledgeBaseChatRequest = {
      question: q,
      k: 5,
      web_search: webSearchEnabled,
      web_search_provider: webSearchProvider,
      ...toScopePayload(chatScope),
    };
    let didSettle = false;
    let activeAbortController: AbortController | null = null;

    try {
      if (!knowledgeBaseId) return;
      const result = await streamKnowledgeBaseAnswer({
        knowledgeBaseId,
        payload: scopedPayload,
        onAbortController: (controller) => {
          activeAbortController = controller;
          streamAbortRef.current = controller;
        },
        onParsedStream: (parsed) => {
          setMessages((prev) =>
            updateAssistantMessage(prev, assistantId, (message) =>
              applyParsedStreamUpdate(message, parsed),
            ),
          );
        },
      });

      if (result.status === "aborted") {
        return;
      }

      if (result.status === "streamed") {
        setMessages((prev) =>
          updateAssistantMessage(prev, assistantId, (message) =>
            finalizeStreamedAssistantAnswer(message, result.parsed),
          ),
        );
        didSettle = true;
      }

      if (result.status === "partial") {
        setMessages((prev) =>
          updateAssistantMessage(prev, assistantId, (message) => ({
            ...applyParsedStreamUpdate(message, result.parsed),
            content: result.content,
            thinking: result.thinking || message.thinking,
          })),
        );
        didSettle = true;
      }

      if (result.status === "fallback") {
        setMessages((prev) =>
          updateAssistantMessage(prev, assistantId, (message) =>
            finalizeFallbackAssistantAnswer(message, result.response),
          ),
        );
        didSettle = true;
      }

      if (result.status === "error") {
        setMessages((prev) =>
          updateAssistantMessage(prev, assistantId, (message) =>
            applyAssistantError(message, result.message),
          ),
        );
        didSettle = true;
      }
    } catch (error) {
      setMessages((prev) =>
        updateAssistantMessage(prev, assistantId, (message) =>
          applyAssistantError(
            message,
            error instanceof Error ? error.message : "请求失败",
          ),
        ),
      );
      didSettle = true;
    } finally {
      const thinkingDurationMs = Date.now() - thinkingStartedAt;
      if (didSettle) {
        notifySettledRef.current = true;
      }
      setMessages((prev) =>
        updateAssistantMessage(prev, assistantId, (message) => ({
          ...message,
          thinkingActive: false,
          thinkingDurationMs,
          webSearchActive: false,
          webSearchProgress: undefined,
        })),
      );
      if (
        activeAbortController &&
        streamAbortRef.current === activeAbortController
      ) {
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
      updateAssistantMessage(prev, assistantId, resetAssistantForRegeneration),
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
