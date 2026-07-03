"use client";

import { useState, useRef, useEffect } from "react";
import ChatPanelView from "@/components/chat/ChatPanelView";
import { useChatConversationHistory } from "@/components/chat/useChatConversationHistory";
import {
  useChatKnowledgeContext,
  type ChatKnowledgeContextActions,
} from "@/components/chat/useChatKnowledgeContext";
import { useChatModelSettings } from "@/components/chat/useChatModelSettings";
import { useChatPanelViewport } from "@/components/chat/useChatPanelViewport";
import { useChatStreaming } from "@/components/chat/useChatStreaming";
import { useChatWebSearchSettings } from "@/components/chat/useChatWebSearchSettings";
import type { Message } from "@/components/chat/types";
import { displayKnowledgeBaseName } from "@/lib/displayNames";

interface Props {
  statsKey?: number;
  sidebarOpen?: boolean;
  sidebarWidth?: number;
  knowledgeBaseId?: number | null;
  knowledgeBaseName?: string;
  isAdmin?: boolean;
  apiAccountsKey?: number;
  onOpenApiAccounts?: () => void;
  conversationOpenRequest?: { id: number; key: number } | null;
  newConversationRequestKey?: number;
  onConversationSaved?: (conversationId: number) => void;
  onOpenVideoNote?: (bvid: string) => void;
}

export default function ChatPanel({
  statsKey,
  knowledgeBaseId,
  knowledgeBaseName,
  isAdmin = false,
  apiAccountsKey = 0,
  onOpenApiAccounts,
  conversationOpenRequest = null,
  newConversationRequestKey = 0,
  onConversationSaved,
  onOpenVideoNote,
}: Props) {
  const knowledgeBaseTitle = knowledgeBaseId
    ? displayKnowledgeBaseName(knowledgeBaseName)
    : "选择知识库";
  const [input, setInput] = useState("");
  const shouldFollowChatScrollRef = useRef(true);
  const knowledgeContextActionsRef = useRef<ChatKnowledgeContextActions>({
    onMessagesClear: () => {},
    onResetConversationIdentity: () => {},
    onResetChat: () => {},
    onStopGenerating: () => {},
    onWebSearchEnabledChange: () => {},
    onWebSearchNoticeClear: () => {},
  });
  const saveSettledMessagesRef = useRef<(messages: Message[]) => void>(
    () => {},
  );

  const {
    chatScope,
    handleScopeChange,
    scopeNotice,
    scopeOptions,
    setChatScope,
    setScopeNotice,
    showScopeNotice,
    stats,
  } = useChatKnowledgeContext({
    actionsRef: knowledgeContextActionsRef,
    knowledgeBaseId,
    statsKey,
  });

  const {
    clearWebSearchNotice,
    closeWebSearchConfig,
    handleSaveWebSearchConfig,
    handleWebSearchChange,
    handleWebSearchProviderChange,
    openWebSearchConfig,
    setWebSearchEnabled,
    setWebSearchProvider,
    setWebSearchApiKey,
    webSearchApiKey,
    webSearchConfig,
    webSearchConfigError,
    webSearchConfigOpen,
    webSearchConfigSaving,
    webSearchEnabled,
    webSearchNotice,
    webSearchProvider,
  } = useChatWebSearchSettings({
    apiAccountsKey,
    isAdmin,
    onOpenApiAccounts,
    onScopeNotice: setScopeNotice,
  });

  const {
    activeProvider,
    closeProviderConfig,
    configApiKey,
    configBaseUrl,
    configError,
    configModel,
    configProvider,
    configSaving,
    configThinkingJson,
    configThinkingMode,
    currentApiSource,
    currentProvider,
    handleSaveProviderConfig,
    handleSwitchModelSource,
    handleSwitchProvider,
    llmChecking,
    llmConfig,
    llmSwitching,
    modelLatencyText,
    modelMenuOpen,
    modelReady,
    modelStatusTitle,
    openProviderConfig,
    providersForMenu,
    setConfigApiKey,
    setConfigBaseUrl,
    setConfigError,
    setConfigModel,
    setConfigThinkingJson,
    setConfigThinkingMode,
    setModelMenuOpen,
    shouldShowAiKeyHint,
    sourceOptions,
  } = useChatModelSettings({
    apiAccountsKey,
    isAdmin,
    onNotice: showScopeNotice,
  });

  const {
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
    send: sendQuestion,
  } = useChatStreaming({
    knowledgeBaseId,
    chatScope,
    webSearchEnabled,
    webSearchProvider,
    shouldFollowChatScrollRef,
    onMessagesSettled: (settledMessages) => {
      saveSettledMessagesRef.current(settledMessages);
    },
  });
  const {
    chatScrollRef,
    endRef,
    handleChatScroll,
    handleComposerChange,
    inputRef,
  } = useChatPanelViewport({
    input,
    messages,
    onInputChange: setInput,
    shouldFollowChatScrollRef,
  });

  const { saveSettledMessages, resetConversationIdentity } =
    useChatConversationHistory({
      chatScope,
      conversationOpenRequest,
      knowledgeBaseId,
      newConversationRequestKey,
      onConversationSaved,
      onInputReset: () => setInput(""),
      onMessagesLoaded: setMessages,
      onNotice: setScopeNotice,
      onResetChat: resetChat,
      onScopeChange: setChatScope,
      onStopGenerating: stopGenerating,
      onWebSearchEnabledChange: setWebSearchEnabled,
      onWebSearchNoticeClear: clearWebSearchNotice,
      onWebSearchProviderChange: setWebSearchProvider,
      statsWorkspaceId: stats?.workspace_id ?? null,
      webSearchEnabled,
      webSearchProvider,
      webSearchProviderFallback: webSearchConfig?.provider || "auto",
    });

  useEffect(() => {
    knowledgeContextActionsRef.current = {
      onMessagesClear: () => setMessages([]),
      onResetConversationIdentity: resetConversationIdentity,
      onResetChat: resetChat,
      onStopGenerating: stopGenerating,
      onWebSearchEnabledChange: setWebSearchEnabled,
      onWebSearchNoticeClear: clearWebSearchNotice,
    };
  }, [
    clearWebSearchNotice,
    resetChat,
    resetConversationIdentity,
    setMessages,
    setWebSearchEnabled,
    stopGenerating,
  ]);

  useEffect(() => {
    saveSettledMessagesRef.current = (settledMessages: Message[]) => {
      void saveSettledMessages(settledMessages);
    };
  }, [saveSettledMessages]);

  const isGenerating = loading || !!regeneratingMessageId;
  const canSend = Boolean(knowledgeBaseId) && !!input.trim() && !isGenerating;

  return (
    <ChatPanelView
      headerProps={{
        knowledgeBaseTitle,
        totalVideos: stats?.total_videos ?? null,
        activeProvider,
        currentApiSource,
        currentProvider,
        isAdmin,
        llmChecking,
        llmConfig,
        llmSwitching,
        menuOpen: modelMenuOpen,
        modelLatencyText,
        modelReady,
        modelStatusTitle,
        providers: providersForMenu,
        setMenuOpen: setModelMenuOpen,
        sourceOptions,
        onConfigureProvider: openProviderConfig,
        onProviderBlocked: (provider) =>
          setScopeNotice(
            provider.enabled ? "需要管理员切换模型" : "需要管理员配置模型",
          ),
        onSwitchModelSource: (apiSource) =>
          void handleSwitchModelSource(apiSource),
        onSwitchProvider: (provider) => void handleSwitchProvider(provider),
      }}
      messages={messages}
      chatScrollRef={chatScrollRef}
      onChatScroll={handleChatScroll}
      emptyStateProps={{
        showAiKeyHint: shouldShowAiKeyHint,
        onOpenApiAccounts,
        onPromptSelect: setInput,
      }}
      messageListProps={{
        copiedMessageId,
        regeneratingMessageId,
        editingMessageId,
        editingQuestion,
        reactionMap,
        endRef,
        onEditingQuestionChange: setEditingQuestion,
        onSubmitEditedQuestion: (messageId) =>
          void handleSubmitEditedQuestion(messageId),
        onCancelEdit: handleCancelEdit,
        onCopyMessage: (messageId, content) =>
          void handleCopyMessage(messageId, content),
        onRegenerate: (assistantId, question) =>
          void handleRegenerate(assistantId, question),
        onReaction: handleReaction,
        onEditQuestion: handleEditQuestion,
        onOpenVideoNote,
      }}
      composerProps={{
        inputRef,
        input,
        knowledgeBaseId,
        isGenerating,
        canSend,
        scopeNotice,
        scopeOptions,
        chatScope,
        webSearchEnabled,
        webSearchProvider,
        webSearchConfig,
        canConfigureWebSearch: Boolean(onOpenApiAccounts) || isAdmin,
        webSearchNotice,
        onInputChange: handleComposerChange,
        onSendQuestion: (question) => {
          setInput("");
          void sendQuestion(question);
        },
        onStopGenerating: stopGenerating,
        onScopeChange: handleScopeChange,
        onWebSearchChange: handleWebSearchChange,
        onWebSearchProviderChange: handleWebSearchProviderChange,
        onConfigureTavily: openWebSearchConfig,
      }}
      webSearchModalProps={
        webSearchConfigOpen
          ? {
              config: webSearchConfig,
              apiKey: webSearchApiKey,
              saving: webSearchConfigSaving,
              error: webSearchConfigError,
              onApiKeyChange: setWebSearchApiKey,
              onClose: () => closeWebSearchConfig(),
              onSave: () => void handleSaveWebSearchConfig(),
            }
          : null
      }
      modelConfigModalProps={
        configProvider
          ? {
              provider: configProvider,
              apiKey: configApiKey,
              baseUrl: configBaseUrl,
              model: configModel,
              thinkingMode: configThinkingMode,
              thinkingJson: configThinkingJson,
              saving: configSaving,
              error: configError,
              onApiKeyChange: setConfigApiKey,
              onBaseUrlChange: setConfigBaseUrl,
              onModelChange: setConfigModel,
              onThinkingModeChange: (mode, json) => {
                setConfigThinkingMode(mode);
                setConfigThinkingJson(json);
              },
              onThinkingJsonChange: setConfigThinkingJson,
              onClearError: () => setConfigError(""),
              onClose: () => closeProviderConfig(),
              onSave: () => void handleSaveProviderConfig(),
            }
          : null
      }
    />
  );
}
