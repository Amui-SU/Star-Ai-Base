"use client";

import { useState, useRef, useEffect, useCallback, type UIEvent } from "react";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import ChatModelStatus from "@/components/chat/ChatModelStatus";
import Composer from "@/components/chat/Composer";
import MessageList from "@/components/chat/MessageList";
import ModelConfigModal from "@/components/chat/ModelConfigModal";
import WebSearchConfigModal from "@/components/chat/WebSearchConfigModal";
import { useChatConversationHistory } from "@/components/chat/useChatConversationHistory";
import { useChatModelSettings } from "@/components/chat/useChatModelSettings";
import { useChatStreaming } from "@/components/chat/useChatStreaming";
import { useChatWebSearchSettings } from "@/components/chat/useChatWebSearchSettings";
import type { Message } from "@/components/chat/types";
import {
  knowledgeBaseApi,
  KnowledgeStats,
  KnowledgeScopeOptions,
} from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  scopeEquals,
  scopeSummary,
} from "@/lib/chatScope";
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
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [scopeOptions, setScopeOptions] = useState<KnowledgeScopeOptions>({
    folders: [],
  });
  const [chatScope, setChatScope] =
    useState<ChatScopeSelection>(EMPTY_CHAT_SCOPE);
  const [scopeNotice, setScopeNotice] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollFrameRef = useRef<number | null>(null);
  const shouldFollowChatScrollRef = useRef(true);
  const scopeNoticeTimerRef = useRef<number | null>(null);
  const saveSettledMessagesRef = useRef<(messages: Message[]) => void>(
    () => {},
  );

  const showScopeNotice = useCallback((message: string, timeoutMs?: number) => {
    setScopeNotice(message);
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
      scopeNoticeTimerRef.current = null;
    }
    if (timeoutMs !== undefined) {
      scopeNoticeTimerRef.current = window.setTimeout(() => {
        setScopeNotice("");
        scopeNoticeTimerRef.current = null;
      }, timeoutMs);
    }
  }, []);

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
    saveSettledMessagesRef.current = (settledMessages: Message[]) => {
      void saveSettledMessages(settledMessages);
    };
  }, [saveSettledMessages]);

  useEffect(() => {
    if (knowledgeBaseId) {
      knowledgeBaseApi
        .stats(knowledgeBaseId)
        .then(setStats)
        .catch(() => {});
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- switching to no knowledge base must clear stale stats immediately.
      setStats(null);
    }
  }, [statsKey, knowledgeBaseId]);

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

  useEffect(() => {
    let cancelled = false;
    /* eslint-disable react-hooks/set-state-in-effect -- knowledge-base changes intentionally reset the chat context before loading scoped options. */
    resetChat();
    resetConversationIdentity();
    setChatScope(EMPTY_CHAT_SCOPE);
    setWebSearchEnabled(false);
    clearWebSearchNotice();
    setScopeNotice("");
    /* eslint-enable react-hooks/set-state-in-effect */
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
      scopeNoticeTimerRef.current = null;
    }

    if (!knowledgeBaseId) {
      setScopeOptions({ folders: [] });
      return () => {
        cancelled = true;
      };
    }

    knowledgeBaseApi
      .getScopeOptions(knowledgeBaseId)
      .then((options) => {
        if (!cancelled) setScopeOptions(options);
      })
      .catch(() => {
        if (!cancelled) setScopeOptions({ folders: [] });
      });

    return () => {
      cancelled = true;
    };
  }, [
    clearWebSearchNotice,
    knowledgeBaseId,
    resetChat,
    resetConversationIdentity,
    setWebSearchEnabled,
  ]);

  useEffect(() => {
    return () => {
      if (scopeNoticeTimerRef.current) {
        window.clearTimeout(scopeNoticeTimerRef.current);
      }
    };
  }, []);

  const handleScopeChange = (next: ChatScopeSelection) => {
    if (scopeEquals(chatScope, next)) return;
    stopGenerating();
    setMessages([]);
    resetConversationIdentity();
    setChatScope(next);
    clearWebSearchNotice();
    setScopeNotice(`提问范围已更新：${scopeSummary(next)}`);
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
    }
    scopeNoticeTimerRef.current = window.setTimeout(() => {
      setScopeNotice("");
      scopeNoticeTimerRef.current = null;
    }, 2200);
  };

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
