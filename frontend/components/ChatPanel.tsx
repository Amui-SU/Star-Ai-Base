"use client";

import { useState, useRef, useEffect, type UIEvent } from "react";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import ChatModelStatus from "@/components/chat/ChatModelStatus";
import Composer from "@/components/chat/Composer";
import MessageList from "@/components/chat/MessageList";
import ModelConfigModal from "@/components/chat/ModelConfigModal";
import WebSearchConfigModal from "@/components/chat/WebSearchConfigModal";
import { useChatConversationHistory } from "@/components/chat/useChatConversationHistory";
import {
  useChatKnowledgeContext,
  type ChatKnowledgeContextActions,
} from "@/components/chat/useChatKnowledgeContext";
import { useChatModelSettings } from "@/components/chat/useChatModelSettings";
import { useChatStreaming } from "@/components/chat/useChatStreaming";
import { useChatWebSearchSettings } from "@/components/chat/useChatWebSearchSettings";
import type { Message } from "@/components/chat/types";
import { displayKnowledgeBaseName } from "@/lib/displayNames";

const CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 96;

function isNearScrollBottom(element: HTMLElement) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD_PX
  );
}

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
}: Props) {
  const knowledgeBaseTitle = knowledgeBaseId
    ? displayKnowledgeBaseName(knowledgeBaseName)
    : "选择知识库";
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollFrameRef = useRef<number | null>(null);
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

  const handleChatScroll = (event: UIEvent<HTMLDivElement>) => {
    const shouldFollow = isNearScrollBottom(event.currentTarget);
    shouldFollowChatScrollRef.current = shouldFollow;
    if (!shouldFollow && scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = null;
    }
  };

  useEffect(() => {
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = null;
    }
    if (!shouldFollowChatScrollRef.current) {
      return;
    }
    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      endRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    });
    return () => {
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    };
  }, [messages]);

  const adjustComposerHeight = (el?: HTMLTextAreaElement | null) => {
    const textarea = el || inputRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 54), 180);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > 180 ? "auto" : "hidden";
  };

  const handleComposerChange = (
    value: string,
    target?: HTMLTextAreaElement | null,
  ) => {
    setInput(value);
    adjustComposerHeight(target);
  };

  const isGenerating = loading || !!regeneratingMessageId;
  const canSend = Boolean(knowledgeBaseId) && !!input.trim() && !isGenerating;

  useEffect(() => {
    adjustComposerHeight();
  }, [input]);

  return (
    <div className="panel-inner">
      <div className="chat-context-row">
        <div className="chat-context-actions">
          <div className="chat-kb-context">
            {knowledgeBaseTitle}
            {stats && (stats.total_videos ?? 0) > 0 && (
              <span className="chat-kb-meta">
                {" "}
                · {stats.total_videos} 个视频
              </span>
            )}
          </div>
          <ChatModelStatus
            activeProvider={activeProvider}
            currentApiSource={currentApiSource}
            currentProvider={currentProvider}
            isAdmin={isAdmin}
            llmChecking={llmChecking}
            llmConfig={llmConfig}
            llmSwitching={llmSwitching}
            menuOpen={modelMenuOpen}
            modelLatencyText={modelLatencyText}
            modelReady={modelReady}
            modelStatusTitle={modelStatusTitle}
            providers={providersForMenu}
            setMenuOpen={setModelMenuOpen}
            sourceOptions={sourceOptions}
            onConfigureProvider={openProviderConfig}
            onProviderBlocked={(provider) =>
              setScopeNotice(
                provider.enabled ? "需要管理员切换模型" : "需要管理员配置模型",
              )
            }
            onSwitchModelSource={(apiSource) =>
              void handleSwitchModelSource(apiSource)
            }
            onSwitchProvider={(provider) => void handleSwitchProvider(provider)}
          />
        </div>
      </div>

      <div className="panel-body">
        <div
          className="chat-scroll"
          ref={chatScrollRef}
          onScroll={handleChatScroll}
        >
          {messages.length === 0 ? (
            <ChatEmptyState
              showAiKeyHint={shouldShowAiKeyHint}
              onOpenApiAccounts={onOpenApiAccounts}
              onPromptSelect={setInput}
            />
          ) : (
            <MessageList
              messages={messages}
              copiedMessageId={copiedMessageId}
              regeneratingMessageId={regeneratingMessageId}
              editingMessageId={editingMessageId}
              editingQuestion={editingQuestion}
              reactionMap={reactionMap}
              endRef={endRef}
              onEditingQuestionChange={setEditingQuestion}
              onSubmitEditedQuestion={(messageId) =>
                void handleSubmitEditedQuestion(messageId)
              }
              onCancelEdit={handleCancelEdit}
              onCopyMessage={(messageId, content) =>
                void handleCopyMessage(messageId, content)
              }
              onRegenerate={(assistantId, question) =>
                void handleRegenerate(assistantId, question)
              }
              onReaction={handleReaction}
              onEditQuestion={handleEditQuestion}
            />
          )}
        </div>
      </div>

      <div className="panel-footer border-transparent bg-transparent flex flex-col items-center gap-2">
        <div className="w-full max-w-3xl mx-auto mt-1">
          {scopeNotice && (
            <div className="scope-notice" aria-live="polite">
              {scopeNotice}
            </div>
          )}
          <Composer
            inputRef={inputRef}
            input={input}
            knowledgeBaseId={knowledgeBaseId}
            isGenerating={isGenerating}
            canSend={canSend}
            scopeOptions={scopeOptions}
            chatScope={chatScope}
            webSearchEnabled={webSearchEnabled}
            webSearchProvider={webSearchProvider}
            webSearchConfig={webSearchConfig}
            canConfigureWebSearch={Boolean(onOpenApiAccounts) || isAdmin}
            webSearchNotice={webSearchNotice}
            onInputChange={handleComposerChange}
            onSend={() => {
              const question = input;
              setInput("");
              void sendQuestion(question);
            }}
            onStopGenerating={stopGenerating}
            onScopeChange={handleScopeChange}
            onWebSearchChange={handleWebSearchChange}
            onWebSearchProviderChange={handleWebSearchProviderChange}
            onConfigureTavily={openWebSearchConfig}
          />
        </div>
        <div className="composer-disclaimer text-[10px] text-(--muted) text-center">
          内容由 AI 生成，请注意甄别。
        </div>
      </div>

      {webSearchConfigOpen && (
        <WebSearchConfigModal
          config={webSearchConfig}
          apiKey={webSearchApiKey}
          saving={webSearchConfigSaving}
          error={webSearchConfigError}
          onApiKeyChange={setWebSearchApiKey}
          onClose={() => closeWebSearchConfig()}
          onSave={() => void handleSaveWebSearchConfig()}
        />
      )}

      {configProvider && (
        <ModelConfigModal
          provider={configProvider}
          apiKey={configApiKey}
          baseUrl={configBaseUrl}
          model={configModel}
          thinkingMode={configThinkingMode}
          thinkingJson={configThinkingJson}
          saving={configSaving}
          error={configError}
          onApiKeyChange={setConfigApiKey}
          onBaseUrlChange={setConfigBaseUrl}
          onModelChange={setConfigModel}
          onThinkingModeChange={(mode, json) => {
            setConfigThinkingMode(mode);
            setConfigThinkingJson(json);
          }}
          onThinkingJsonChange={setConfigThinkingJson}
          onClearError={() => setConfigError("")}
          onClose={() => closeProviderConfig()}
          onSave={() => void handleSaveProviderConfig()}
        />
      )}
    </div>
  );
}
