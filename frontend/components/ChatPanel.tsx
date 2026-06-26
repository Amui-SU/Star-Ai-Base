"use client";

import { useState, useRef, useEffect, useCallback, type UIEvent } from "react";
import Image from "next/image";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import Composer from "@/components/chat/Composer";
import MessageList from "@/components/chat/MessageList";
import ModelConfigModal from "@/components/chat/ModelConfigModal";
import WebSearchConfigModal from "@/components/chat/WebSearchConfigModal";
import { useChatStreaming } from "@/components/chat/useChatStreaming";
import type { Message, ModelConfigProvider } from "@/components/chat/types";
import {
  chatApi,
  chatHistoryApi,
  knowledgeBaseApi,
  KnowledgeStats,
  LLMHealthResponse,
  LLMConfigResponse,
  LLMProvider,
  LLMApiSource,
  KnowledgeScopeOptions,
  WebSearchConfigResponse,
  WebSearchProvider,
  type ChatConversation,
  type ChatConversationSaveRequest,
  type ChatConversationScope,
} from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  scopeEquals,
  scopeSummary,
} from "@/lib/chatScope";
import { displayKnowledgeBaseName } from "@/lib/displayNames";
import { LLM_PROVIDER_PRESETS, providerLogoMap } from "@/lib/providers";
import {
  formatThinkingConfig,
  inferThinkingMode,
  parseThinkingConfig,
  type ThinkingMode,
} from "@/lib/thinkingConfig";

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
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [webSearchProvider, setWebSearchProvider] =
    useState<WebSearchProvider>("auto");
  const [webSearchConfig, setWebSearchConfig] =
    useState<WebSearchConfigResponse | null>(null);
  const [webSearchConfigOpen, setWebSearchConfigOpen] = useState(false);
  const [webSearchApiKey, setWebSearchApiKey] = useState("");
  const [webSearchConfigSaving, setWebSearchConfigSaving] = useState(false);
  const [webSearchConfigError, setWebSearchConfigError] = useState("");
  const [scopeNotice, setScopeNotice] = useState("");
  const [webSearchNotice, setWebSearchNotice] = useState("");
  const [llmHealth, setLlmHealth] = useState<LLMHealthResponse | null>(null);
  const [llmChecking, setLlmChecking] = useState(false);
  const [llmConfig, setLlmConfig] = useState<LLMConfigResponse | null>(null);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [configProvider, setConfigProvider] =
    useState<ModelConfigProvider | null>(null);
  const [configApiKey, setConfigApiKey] = useState("");
  const [configBaseUrl, setConfigBaseUrl] = useState("");
  const [configModel, setConfigModel] = useState("");
  const [configThinkingMode, setConfigThinkingMode] =
    useState<ThinkingMode>("off");
  const [configThinkingJson, setConfigThinkingJson] = useState("{}");
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState("");
  const [currentConversationId, setCurrentConversationId] = useState<
    number | null
  >(null);
  const lastConversationRequestKeyRef = useRef<number | null>(null);
  const lastNewConversationRequestKeyRef = useRef(newConversationRequestKey);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);
  const scrollFrameRef = useRef<number | null>(null);
  const shouldFollowChatScrollRef = useRef(true);
  const scopeNoticeTimerRef = useRef<number | null>(null);

  const scopeToHistoryScope = useCallback(
    (scope: ChatScopeSelection): ChatConversationScope => ({
      folder_ids: [...scope.folderIds],
      bvids: [...scope.bvids],
    }),
    [],
  );

  const historyScopeToSelection = useCallback(
    (scope?: ChatConversationScope | null): ChatScopeSelection => ({
      folderIds: scope?.folder_ids ?? [],
      bvids: scope?.bvids ?? [],
    }),
    [],
  );

  const persistConversation = useCallback(
    async (settledMessages: Message[]) => {
      if (settledMessages.length === 0) return;
      const payload: ChatConversationSaveRequest = {
        workspace_id: stats?.workspace_id ?? null,
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
        setScopeNotice(err instanceof Error ? err.message : "保存历史失败");
      }
    },
    [
      chatScope,
      currentConversationId,
      knowledgeBaseId,
      onConversationSaved,
      scopeToHistoryScope,
      stats?.workspace_id,
      webSearchEnabled,
      webSearchProvider,
    ],
  );

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
      void persistConversation(settledMessages);
    },
  });
  const openProviderConfig = (provider: ModelConfigProvider) => {
    if (!isAdmin) {
      setScopeNotice("需要管理员配置模型");
      return;
    }
    setConfigProvider(provider);
    setConfigApiKey("");
    setConfigBaseUrl(provider.base_url || "");
    setConfigModel(provider.model || "");
    const thinkingConfig = provider.thinking_config || {};
    const thinkingTemplate = provider.thinking_template || {};
    const mode = inferThinkingMode(thinkingConfig, thinkingTemplate);
    setConfigThinkingMode(mode);
    setConfigThinkingJson(
      formatThinkingConfig(
        mode === "standard" ? thinkingTemplate : thinkingConfig,
      ),
    );
    setConfigError("");
    setModelMenuOpen(false);
  };

  const closeProviderConfig = (force = false) => {
    if (configSaving && !force) return;
    setConfigProvider(null);
    setConfigApiKey("");
    setConfigBaseUrl("");
    setConfigModel("");
    setConfigThinkingMode("off");
    setConfigThinkingJson("{}");
    setConfigError("");
  };

  const handleSaveProviderConfig = async () => {
    if (!configProvider || configSaving) return;
    if (!configProvider.enabled && !configApiKey.trim()) {
      setConfigError("请填写 API Key");
      return;
    }
    let thinkingConfig: Record<string, unknown> | undefined;
    if (configThinkingMode === "custom") {
      try {
        thinkingConfig = parseThinkingConfig(configThinkingJson);
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : "思考配置无效");
        return;
      }
    }
    setConfigSaving(true);
    setConfigError("");
    try {
      const saved = await chatApi.saveModelProviderConfig({
        provider: configProvider.provider,
        api_key: configApiKey.trim() || undefined,
        base_url: configBaseUrl.trim() || undefined,
        model: configModel.trim() || undefined,
        thinking_mode: configThinkingMode,
        thinking_config: thinkingConfig,
      });
      const [cfg, health] = await Promise.all([
        chatApi.getModelConfig(),
        chatApi.health(),
      ]);
      setLlmConfig(cfg);
      setLlmHealth(health);
      setScopeNotice(`模型与思考配置验证成功 · ${saved.latency_ms}ms`);
      if (scopeNoticeTimerRef.current) {
        window.clearTimeout(scopeNoticeTimerRef.current);
      }
      scopeNoticeTimerRef.current = window.setTimeout(() => {
        setScopeNotice("");
        scopeNoticeTimerRef.current = null;
      }, 2600);
      closeProviderConfig(true);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setConfigSaving(false);
    }
  };

  const openWebSearchConfig = () => {
    if (onOpenApiAccounts) {
      setWebSearchConfigError("");
      setWebSearchNotice("请在 AI 服务密钥中添加 Tavily");
      onOpenApiAccounts();
      return;
    }
    if (!isAdmin) {
      setWebSearchConfigError("");
      setWebSearchNotice("Tavily 需要管理员配置");
      return;
    }
    setWebSearchApiKey("");
    setWebSearchConfigError("");
    setWebSearchConfigOpen(true);
  };

  const closeWebSearchConfig = (force = false) => {
    if (webSearchConfigSaving && !force) return;
    setWebSearchConfigOpen(false);
    setWebSearchApiKey("");
    setWebSearchConfigError("");
  };

  const handleSaveWebSearchConfig = async () => {
    if (webSearchConfigSaving) return;
    const apiKey = webSearchApiKey.trim();
    if (!webSearchConfig?.tavily_configured && !apiKey) {
      setWebSearchConfigError("请填写 Tavily API Key");
      return;
    }
    setWebSearchConfigSaving(true);
    setWebSearchConfigError("");
    try {
      const cfg = await chatApi.saveWebSearchConfig({
        provider: "tavily",
        tavily_api_key: apiKey || undefined,
        fallback_html: webSearchConfig?.fallback_html ?? true,
        tavily_search_depth: webSearchConfig?.tavily_search_depth || "basic",
      });
      setWebSearchConfig(cfg);
      setWebSearchProvider("tavily");
      setWebSearchEnabled(true);
      setWebSearchNotice("联网搜索已开启");
      closeWebSearchConfig(true);
    } catch (err) {
      setWebSearchConfigError(
        err instanceof Error ? err.message : "保存联网搜索配置失败",
      );
    } finally {
      setWebSearchConfigSaving(false);
    }
  };

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

  useEffect(() => {
    let cancelled = false;
    const loadConfig = async () => {
      try {
        const [cfg, webCfg] = await Promise.all([
          chatApi.getModelConfig(),
          chatApi.getWebSearchConfig(),
        ]);
        if (!cancelled) {
          setLlmConfig(cfg);
          setWebSearchConfig(webCfg);
          setWebSearchProvider(webCfg.provider || "auto");
        }
      } catch {
        // 忽略配置加载失败，不影响聊天主流程
      }
    };
    const check = async () => {
      setLlmChecking(true);
      try {
        const res = await chatApi.health();
        if (!cancelled) setLlmHealth(res);
      } catch {
        if (!cancelled) {
          setLlmHealth({
            status: "down",
            message: "健康检查失败",
            model: "unknown",
            provider: "unknown",
          });
        }
      } finally {
        if (!cancelled) setLlmChecking(false);
      }
    };

    loadConfig();
    check();
    const timer = window.setInterval(check, 45000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [apiAccountsKey]);

  const handleSwitchProvider = async (provider: LLMProvider) => {
    if (llmSwitching) return;
    setLlmSwitching(true);
    try {
      await chatApi.setModelProvider(provider);
      const [cfg, health] = await Promise.all([
        chatApi.getModelConfig(),
        chatApi.health(),
      ]);
      setLlmConfig(cfg);
      setLlmHealth(health);
    } catch (err) {
      setLlmHealth({
        status: "down",
        message: err instanceof Error ? err.message : "模型切换失败",
        model: "unknown",
        provider: "unknown",
      });
    } finally {
      setLlmSwitching(false);
    }
  };

  const handleSwitchModelSource = async (apiSource: LLMApiSource) => {
    if (llmSwitching || llmConfig?.current_api_source === apiSource) return;
    setLlmSwitching(true);
    try {
      const cfg = await chatApi.setModelSource(apiSource);
      const health = await chatApi.health();
      setLlmConfig(cfg);
      setLlmHealth(health);
    } catch (err) {
      setScopeNotice(err instanceof Error ? err.message : "模型来源切换失败");
    } finally {
      setLlmSwitching(false);
    }
  };

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
    if (!modelMenuOpen) return;
    const onClickOutside = (event: MouseEvent) => {
      if (!modelMenuRef.current) return;
      if (!modelMenuRef.current.contains(event.target as Node)) {
        setModelMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [modelMenuOpen]);

  useEffect(() => {
    let cancelled = false;
    /* eslint-disable react-hooks/set-state-in-effect -- knowledge-base changes intentionally reset the chat context before loading scoped options. */
    resetChat();
    setCurrentConversationId(null);
    setChatScope(EMPTY_CHAT_SCOPE);
    setWebSearchEnabled(false);
    setWebSearchNotice("");
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
  }, [knowledgeBaseId, resetChat]);

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
    setCurrentConversationId(null);
    setChatScope(next);
    setWebSearchNotice("");
    setScopeNotice(`提问范围已更新：${scopeSummary(next)}`);
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
    }
    scopeNoticeTimerRef.current = window.setTimeout(() => {
      setScopeNotice("");
      scopeNoticeTimerRef.current = null;
    }, 2200);
  };

  const handleWebSearchChange = (enabled: boolean) => {
    const notice = enabled ? "联网搜索已开启" : "联网搜索已关闭";
    setWebSearchEnabled(enabled);
    if (enabled) {
      setWebSearchProvider("auto");
    }
    setWebSearchNotice(notice);
    setScopeNotice("");
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
    }
    scopeNoticeTimerRef.current = window.setTimeout(() => {
      setWebSearchNotice("");
      scopeNoticeTimerRef.current = null;
    }, 2200);
  };

  const handleWebSearchProviderChange = (provider: WebSearchProvider) => {
    if (
      provider === "tavily" &&
      !webSearchConfig?.tavily_configured &&
      !isAdmin &&
      !onOpenApiAccounts
    ) {
      setWebSearchNotice("Tavily 需要管理员配置");
      return;
    }
    setWebSearchProvider(provider);
    setWebSearchEnabled(true);
    if (provider === "tavily" && !webSearchConfig?.tavily_configured) {
      setWebSearchNotice("请先添加 Tavily 服务密钥");
      openWebSearchConfig();
    }
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

  const handleOpenConversation = useCallback(
    async (conversationId: number) => {
      try {
        const conversation: ChatConversation =
          await chatHistoryApi.get(conversationId);
        stopGenerating();
        setMessages(
          conversation.messages.map((message) => ({
            id: `history-${message.id}`,
            role: message.role,
            content: message.content,
            thinking: message.thinking,
            sources: message.sources,
            webSearch: message.web_search,
          })),
        );
        setChatScope(historyScopeToSelection(conversation.scope));
        setWebSearchEnabled(conversation.web_search);
        setWebSearchProvider(conversation.web_search_provider || "auto");
        setCurrentConversationId(conversation.id);
        setInput("");
      } catch (err) {
        setScopeNotice(err instanceof Error ? err.message : "打开历史失败");
      }
    },
    [historyScopeToSelection, setMessages, stopGenerating],
  );

  const handleNewConversation = useCallback(() => {
    stopGenerating();
    resetChat();
    setCurrentConversationId(null);
    setChatScope(EMPTY_CHAT_SCOPE);
    setWebSearchEnabled(false);
    setWebSearchProvider(webSearchConfig?.provider || "auto");
    setWebSearchNotice("");
    setScopeNotice("");
    setInput("");
  }, [resetChat, stopGenerating, webSearchConfig?.provider]);

  useEffect(() => {
    if (!conversationOpenRequest) return;
    if (lastConversationRequestKeyRef.current === conversationOpenRequest.key) {
      return;
    }
    lastConversationRequestKeyRef.current = conversationOpenRequest.key;
    void handleOpenConversation(conversationOpenRequest.id);
  }, [conversationOpenRequest, handleOpenConversation]);

  useEffect(() => {
    if (
      lastNewConversationRequestKeyRef.current === newConversationRequestKey
    ) {
      return;
    }
    lastNewConversationRequestKeyRef.current = newConversationRequestKey;
    handleNewConversation();
  }, [handleNewConversation, newConversationRequestKey]);

  const isGenerating = loading || !!regeneratingMessageId;
  const canSend = Boolean(knowledgeBaseId) && !!input.trim() && !isGenerating;
  const remoteProviders = llmConfig?.providers ?? [];
  const currentApiSource: LLMApiSource =
    llmConfig?.current_api_source === "personal" ? "personal" : "official";
  const sourceAvailability = {
    official: remoteProviders.some(
      (provider) => provider.official_enabled ?? provider.enabled,
    ),
    personal: remoteProviders.some(
      (provider) => provider.personal_enabled ?? provider.enabled,
    ),
  };
  const hasEnabledCurrentSource = remoteProviders.some(
    (provider) => provider.enabled,
  );
  const shouldShowAiKeyHint =
    Boolean(llmConfig) &&
    currentApiSource === "personal" &&
    !hasEnabledCurrentSource;
  const remoteProviderMap = new Map(
    remoteProviders.map((p) => [p.provider, p]),
  );
  const sourceOptions: Array<{
    value: LLMApiSource;
    label: string;
    hint: string;
    enabled: boolean;
  }> = [
    {
      value: "official",
      label: "官方",
      hint: "付费通道",
      enabled: sourceAvailability.official,
    },
    {
      value: "personal",
      label: "个人",
      hint: "自带 Key",
      enabled: true,
    },
  ];
  const providersForMenu = [
    ...LLM_PROVIDER_PRESETS.map((base) => {
      const remote = remoteProviderMap.get(base.provider);
      return {
        provider: base.provider,
        label: remote?.label ?? base.label,
        enabled: remote?.enabled ?? false,
        official_enabled: remote?.official_enabled ?? false,
        personal_enabled: remote?.personal_enabled ?? false,
        model: remote?.model ?? base.model,
        base_url: remote?.base_url,
        thinking_config: remote?.thinking_config ?? {},
        thinking_template: remote?.thinking_template ?? {},
      };
    }),
    ...remoteProviders.filter(
      (p) => !LLM_PROVIDER_PRESETS.some((b) => b.provider === p.provider),
    ),
  ];
  const currentProvider =
    llmConfig?.current_provider ?? providersForMenu[0]?.provider;
  const activeProvider = providersForMenu.find(
    (p) => p.provider === currentProvider,
  );
  const modelReady = llmHealth?.status === "ok" || llmHealth?.status === "up";
  const modelStatusText = llmChecking
    ? "检查中"
    : modelReady
      ? "模型就绪"
      : "模型异常";
  const modelLatencyText =
    !llmChecking && llmHealth?.latency_ms != null
      ? `${llmHealth.latency_ms}ms`
      : "-- ms";
  const modelStatusTitle = activeProvider
    ? `${modelStatusText} · ${modelLatencyText} · ${activeProvider.label} · ${activeProvider.model}`
    : `${modelStatusText} · ${modelLatencyText}`;

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
          <div className="model-status-card">
            <div className="relative" ref={modelMenuRef}>
              <button
                type="button"
                disabled={llmSwitching}
                onClick={() => setModelMenuOpen((v) => !v)}
                className={`model-selector-trigger ${
                  llmChecking ? "empty" : modelReady ? "ok" : "alert"
                }`}
                title={modelStatusTitle}
                aria-label="模型选择"
              >
                <Image
                  src={
                    activeProvider
                      ? providerLogoMap.get(activeProvider.provider) ||
                        "/logos/qwen-icon.png"
                      : "/logos/qwen-icon.png"
                  }
                  alt={
                    activeProvider
                      ? `${activeProvider.label} logo`
                      : "model logo"
                  }
                  width={16}
                  height={16}
                  unoptimized
                  className="model-health-logo"
                />
                <span className="model-latency">{modelLatencyText}</span>
              </button>

              {modelMenuOpen && (
                <div className="model-provider-menu">
                  <div className="model-source-switch" aria-label="模型来源">
                    {sourceOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        aria-label={option.label}
                        aria-pressed={currentApiSource === option.value}
                        disabled={
                          llmSwitching ||
                          !llmConfig ||
                          (option.value === "official" && !option.enabled)
                        }
                        className={`model-source-option ${
                          currentApiSource === option.value ? "active" : ""
                        }`}
                        onClick={() =>
                          void handleSwitchModelSource(option.value)
                        }
                        title={
                          option.value === "official" && !option.enabled
                            ? "官方通道暂未开通"
                            : `${option.label} · ${option.hint}`
                        }
                      >
                        <span>{option.label}</span>
                        <small>{option.hint}</small>
                      </button>
                    ))}
                  </div>
                  {providersForMenu.map((p) => (
                    <div key={p.provider} className="model-provider-row">
                      <button
                        type="button"
                        disabled={
                          llmSwitching || !llmConfig || (!isAdmin && !p.enabled)
                        }
                        onClick={() => {
                          if (!isAdmin) {
                            setScopeNotice(
                              p.enabled
                                ? "需要管理员切换模型"
                                : "需要管理员配置模型",
                            );
                            setModelMenuOpen(false);
                            return;
                          }
                          if (p.enabled) {
                            void handleSwitchProvider(p.provider);
                          } else {
                            openProviderConfig(p);
                          }
                          setModelMenuOpen(false);
                        }}
                        className={`model-provider-option ${
                          p.provider === currentProvider ? "active" : ""
                        }`}
                        title={
                          p.enabled
                            ? `${p.label} · ${p.model}`
                            : `${p.label}（${
                                currentApiSource === "official"
                                  ? "未开通"
                                  : "未配置"
                              }）`
                        }
                      >
                        <span className="inline-flex min-w-0 flex-1 items-center gap-1.5">
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-(--paper)">
                            <Image
                              src={
                                providerLogoMap.get(p.provider) ||
                                "/logos/qwen-icon.png"
                              }
                              alt={`${p.label} logo`}
                              width={12}
                              height={12}
                              unoptimized
                              className="rounded-sm object-contain"
                            />
                          </span>
                          <span className="min-w-0">
                            <span className="block text-[10px] font-semibold text-(--ink-soft) leading-tight truncate">
                              {p.label}
                            </span>
                            <span className="block text-[9px] text-(--muted) leading-tight truncate mt-1">
                              {p.model}
                            </span>
                          </span>
                        </span>
                        <span
                          className={`status-pill ${
                            p.enabled
                              ? p.provider === currentProvider
                                ? "ok"
                                : "empty"
                              : "partial"
                          }`}
                        >
                          {p.enabled
                            ? p.provider === currentProvider
                              ? "当前"
                              : "可用"
                            : currentApiSource === "official"
                              ? "未开通"
                              : "未配置"}
                        </span>
                      </button>
                      {p.enabled && isAdmin && (
                        <button
                          type="button"
                          className="model-provider-config-btn"
                          onClick={() => openProviderConfig(p)}
                          title={`配置 ${p.label}`}
                          aria-label={`配置 ${p.label}`}
                        >
                          配置
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
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
