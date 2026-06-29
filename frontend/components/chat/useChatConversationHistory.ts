"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Message } from "@/components/chat/types";
import {
  chatHistoryApi,
  type ChatConversation,
  type ChatConversationSaveRequest,
  type ChatConversationScope,
  type WebSearchProvider,
} from "@/lib/api";
import { EMPTY_CHAT_SCOPE, type ChatScopeSelection } from "@/lib/chatScope";

interface ConversationOpenRequest {
  id: number;
  key: number;
}

interface UseChatConversationHistoryOptions {
  chatScope: ChatScopeSelection;
  conversationOpenRequest?: ConversationOpenRequest | null;
  knowledgeBaseId?: number | null;
  newConversationRequestKey: number;
  onConversationSaved?: (conversationId: number) => void;
  onInputReset: () => void;
  onMessagesLoaded: (messages: Message[]) => void;
  onNotice: (message: string) => void;
  onResetChat: () => void;
  onScopeChange: (scope: ChatScopeSelection) => void;
  onStopGenerating: () => void;
  onWebSearchEnabledChange: (enabled: boolean) => void;
  onWebSearchNoticeClear: () => void;
  onWebSearchProviderChange: (provider: WebSearchProvider) => void;
  statsWorkspaceId?: number | null;
  webSearchEnabled: boolean;
  webSearchProvider: WebSearchProvider;
  webSearchProviderFallback?: WebSearchProvider;
}

function scopeToHistoryScope(scope: ChatScopeSelection): ChatConversationScope {
  return {
    folder_ids: [...scope.folderIds],
    bvids: [...scope.bvids],
  };
}

function historyScopeToSelection(
  scope?: ChatConversationScope | null,
): ChatScopeSelection {
  return {
    folderIds: scope?.folder_ids ?? [],
    bvids: scope?.bvids ?? [],
  };
}

function messagesFromConversation(conversation: ChatConversation): Message[] {
  return conversation.messages.map((message) => ({
    id: `history-${message.id}`,
    role: message.role,
    content: message.content,
    thinking: message.thinking,
    sources: message.sources,
    webSearch: message.web_search,
  }));
}

export function useChatConversationHistory({
  chatScope,
  conversationOpenRequest = null,
  knowledgeBaseId,
  newConversationRequestKey,
  onConversationSaved,
  onInputReset,
  onMessagesLoaded,
  onNotice,
  onResetChat,
  onScopeChange,
  onStopGenerating,
  onWebSearchEnabledChange,
  onWebSearchNoticeClear,
  onWebSearchProviderChange,
  statsWorkspaceId,
  webSearchEnabled,
  webSearchProvider,
  webSearchProviderFallback = "auto",
}: UseChatConversationHistoryOptions) {
  const [currentConversationId, setCurrentConversationId] = useState<
    number | null
  >(null);
  const lastConversationRequestKeyRef = useRef<number | null>(null);
  const lastNewConversationRequestKeyRef = useRef(newConversationRequestKey);

  const saveSettledMessages = useCallback(
    async (settledMessages: Message[]) => {
      if (settledMessages.length === 0) return;
      const payload: ChatConversationSaveRequest = {
        workspace_id: statsWorkspaceId ?? null,
        knowledge_base_id: knowledgeBaseId ?? null,
        scope: scopeToHistoryScope(chatScope),
        web_search: webSearchEnabled,
        web_search_provider: webSearchProvider,
        messages: settledMessages.map((message) => ({
          role: message.role,
          content: message.content,
          thinking: message.thinking,
          sources: message.sources,
          web_search: message.webSearch,
        })),
      };

      try {
        const saved = currentConversationId
          ? await chatHistoryApi.update(currentConversationId, payload)
          : await chatHistoryApi.create(payload);
        setCurrentConversationId(saved.id);
        onConversationSaved?.(saved.id);
      } catch (err) {
        onNotice(err instanceof Error ? err.message : "保存历史失败");
      }
    },
    [
      chatScope,
      currentConversationId,
      knowledgeBaseId,
      onConversationSaved,
      onNotice,
      statsWorkspaceId,
      webSearchEnabled,
      webSearchProvider,
    ],
  );

  const resetConversationIdentity = useCallback(() => {
    setCurrentConversationId(null);
  }, []);

  const openConversation = useCallback(
    async (conversationId: number) => {
      try {
        const conversation = await chatHistoryApi.get(conversationId);
        onStopGenerating();
        onMessagesLoaded(messagesFromConversation(conversation));
        onScopeChange(historyScopeToSelection(conversation.scope));
        onWebSearchEnabledChange(conversation.web_search);
        onWebSearchProviderChange(conversation.web_search_provider || "auto");
        setCurrentConversationId(conversation.id);
        onInputReset();
      } catch (err) {
        onNotice(err instanceof Error ? err.message : "打开历史失败");
      }
    },
    [
      onInputReset,
      onMessagesLoaded,
      onNotice,
      onScopeChange,
      onStopGenerating,
      onWebSearchEnabledChange,
      onWebSearchProviderChange,
    ],
  );

  const startNewConversation = useCallback(() => {
    onStopGenerating();
    onResetChat();
    setCurrentConversationId(null);
    onScopeChange(EMPTY_CHAT_SCOPE);
    onWebSearchEnabledChange(false);
    onWebSearchProviderChange(webSearchProviderFallback);
    onWebSearchNoticeClear();
    onNotice("");
    onInputReset();
  }, [
    onInputReset,
    onNotice,
    onResetChat,
    onScopeChange,
    onStopGenerating,
    onWebSearchEnabledChange,
    onWebSearchNoticeClear,
    onWebSearchProviderChange,
    webSearchProviderFallback,
  ]);

  useEffect(() => {
    if (!conversationOpenRequest) return;
    if (lastConversationRequestKeyRef.current === conversationOpenRequest.key) {
      return;
    }
    lastConversationRequestKeyRef.current = conversationOpenRequest.key;
    void openConversation(conversationOpenRequest.id);
  }, [conversationOpenRequest, openConversation]);

  useEffect(() => {
    if (
      lastNewConversationRequestKeyRef.current === newConversationRequestKey
    ) {
      return;
    }
    lastNewConversationRequestKeyRef.current = newConversationRequestKey;
    startNewConversation();
  }, [newConversationRequestKey, startNewConversation]);

  return {
    saveSettledMessages,
    resetConversationIdentity,
  };
}
