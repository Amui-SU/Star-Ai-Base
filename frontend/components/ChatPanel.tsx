"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Image from "next/image";
import ChatScopePicker from "@/components/ChatScopePicker";
import ThinkingProcess from "@/components/ThinkingProcess";
import {
  chatApi,
  knowledgeBaseApi,
  KnowledgeStats,
  LLMHealthResponse,
  LLMConfigResponse,
  LLMProvider,
  KnowledgeBaseChatRequest,
  KnowledgeScopeOptions,
  ChatWebSearchStatus,
  WebSearchConfigResponse,
  WebSearchProvider,
} from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  scopeEquals,
  scopeSummary,
  toScopePayload,
} from "@/lib/chatScope";
import { parseChatStream } from "@/lib/chatStream";
import {
  formatThinkingConfig,
  inferThinkingMode,
  parseThinkingConfig,
  type ThinkingMode,
} from "@/lib/thinkingConfig";
import { getLocalAuthHeaders } from "@/lib/localConnection";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  thinkingActive?: boolean;
  thinkingStartedAt?: number;
  thinkingDurationMs?: number;
  webSearchActive?: boolean;
  webSearchProgress?: string;
  sources?: Array<{
    bvid?: string;
    title: string;
    url: string;
    type?: "knowledge" | "web" | string;
  }>;
  webSearch?: ChatWebSearchStatus | null;
}
type Reaction = "like" | "dislike" | null;

const CHAT_STREAM_IDLE_TIMEOUT_MS = 90_000;

interface Props {
  statsKey?: number;
  sidebarOpen?: boolean;
  sidebarWidth?: number;
  knowledgeBaseId?: number | null;
  knowledgeBaseName?: string;
}

function MarkdownCode({
  inline,
  className,
  children,
  ...props
}: {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const codeText = String(children ?? "").replace(/\n$/, "");
  const languageMatch = /language-([\w-]+)/.exec(className || "");
  const language = languageMatch?.[1] || "text";

  if (inline) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(codeText);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = codeText;
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="code-block-wrap">
      <div className="code-block-toolbar">
        <span className="code-block-language">{language}</span>
        <button
          type="button"
          className="code-copy-btn"
          onClick={() => void handleCopy()}
        >
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre>
        <code className={className} {...props}>
          {codeText}
        </code>
      </pre>
    </div>
  );
}

export default function ChatPanel({
  statsKey,
  knowledgeBaseId,
  knowledgeBaseName,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [regeneratingMessageId, setRegeneratingMessageId] = useState<
    string | null
  >(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingQuestion, setEditingQuestion] = useState("");
  const [reactionMap, setReactionMap] = useState<Record<string, Reaction>>({});
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
  const [configProvider, setConfigProvider] = useState<{
    provider: string;
    label: string;
    model: string;
    base_url?: string;
    enabled?: boolean;
    thinking_config?: Record<string, unknown>;
    thinking_template?: Record<string, unknown>;
  } | null>(null);
  const [configApiKey, setConfigApiKey] = useState("");
  const [configBaseUrl, setConfigBaseUrl] = useState("");
  const [configModel, setConfigModel] = useState("");
  const [configThinkingMode, setConfigThinkingMode] =
    useState<ThinkingMode>("off");
  const [configThinkingJson, setConfigThinkingJson] = useState("{}");
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const scrollFrameRef = useRef<number | null>(null);
  const scopeNoticeTimerRef = useRef<number | null>(null);
  const providerLogoMap: Record<string, string> = {
    deepseek: "/logos/deepseek-icon.png",
    dashscope: "/logos/dashscope-icon.png",
    openai: "/logos/openai-icon.png",
    kimi: "/logos/kimi-icon.png",
    siliconflow: "/logos/siliconflow-icon.png",
    zhipu: "/logos/zhipu-icon.png",
  };
  const builtInProviders: Array<{
    provider: string;
    label: string;
    model: string;
  }> = [
    { provider: "dashscope", label: "阿里云 DashScope", model: "qwen-max" },
    { provider: "deepseek", label: "DeepSeek", model: "deepseek-chat" },
    { provider: "openai", label: "OpenAI", model: "gpt-4o-mini" },
    { provider: "kimi", label: "Moonshot Kimi", model: "moonshot-v1-8k" },
    {
      provider: "siliconflow",
      label: "SiliconFlow",
      model: "Qwen/Qwen2.5-7B-Instruct",
    },
    { provider: "zhipu", label: "智谱 GLM", model: "glm-4-flash" },
  ];

  const openProviderConfig = (provider: {
    provider: string;
    label: string;
    model: string;
    base_url?: string;
    enabled?: boolean;
    thinking_config?: Record<string, unknown>;
    thinking_template?: Record<string, unknown>;
  }) => {
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
  }, []);

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

  useEffect(() => {
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
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
      } catch (fallbackError) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `错误: ${fallbackError instanceof Error ? fallbackError.message : "请求失败"}`,
                  webSearchActive: false,
                  webSearchProgress: undefined,
                }
              : m,
          ),
        );
      }
    } finally {
      if (streamIdleTimer !== null) {
        window.clearTimeout(streamIdleTimer);
      }
      const thinkingDurationMs = Date.now() - thinkingStartedAt;
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

  const stopGenerating = () => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    setLoading(false);
    setRegeneratingMessageId(null);
  };

  useEffect(() => {
    let cancelled = false;
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    setLoading(false);
    setRegeneratingMessageId(null);
    setMessages([]);
    setChatScope(EMPTY_CHAT_SCOPE);
    setWebSearchEnabled(false);
    setWebSearchNotice("");
    setScopeNotice("");
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
  }, [knowledgeBaseId]);

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
    setWebSearchProvider(provider);
    setWebSearchEnabled(true);
    if (provider === "tavily" && !webSearchConfig?.tavily_configured) {
      openWebSearchConfig();
    }
  };

  const extractThinkingFromContent = (
    rawText: string,
  ): { thinking: string; answer: string } => {
    const text = String(rawText || "");
    const pattern = /<(?:thinking|think)>([\s\S]*?)<\/(?:thinking|think)>/gi;
    const matches = [...text.matchAll(pattern)];
    if (!matches.length) {
      return { thinking: "", answer: text };
    }
    const thinking = matches
      .map((m) => (m[1] || "").trim())
      .filter(Boolean)
      .join("\n\n");
    const answer = text.replace(pattern, "").trim();
    return { thinking, answer };
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

  const handleCopyMessage = async (messageId: string, content: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopiedMessageId(messageId);
      window.setTimeout(
        () => setCopiedMessageId((prev) => (prev === messageId ? null : prev)),
        1500,
      );
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

  const send = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    const userId = Date.now().toString();
    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: q },
      { id: assistantId, role: "assistant", content: "", sources: [] },
    ]);
    setLoading(true);

    try {
      await fetchAssistantAnswer(q, assistantId);
    } finally {
      setLoading(false);
    }
  };

  const isGenerating = loading || !!regeneratingMessageId;
  const canSend = !!input.trim() && !isGenerating;
  const remoteProviders = llmConfig?.providers ?? [];
  const remoteProviderMap = new Map(
    remoteProviders.map((p) => [p.provider, p]),
  );
  const providersForMenu = [
    ...builtInProviders.map((base) => {
      const remote = remoteProviderMap.get(base.provider);
      return {
        provider: base.provider,
        label: remote?.label ?? base.label,
        enabled: remote?.enabled ?? false,
        model: remote?.model ?? base.model,
        base_url: remote?.base_url,
        thinking_config: remote?.thinking_config ?? {},
        thinking_template: remote?.thinking_template ?? {},
      };
    }),
    ...remoteProviders.filter(
      (p) => !builtInProviders.some((b) => b.provider === p.provider),
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
        <div className="chat-kb-context">
          {knowledgeBaseName || "选择知识库"}
          {stats && (stats.total_videos ?? 0) > 0 && (
            <span className="chat-kb-meta"> · {stats.total_videos} 个视频</span>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5">
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
                      ? providerLogoMap[activeProvider.provider] ||
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
                  {providersForMenu.map((p) => (
                    <div key={p.provider} className="model-provider-row">
                      <button
                        type="button"
                        disabled={llmSwitching || !llmConfig}
                        onClick={() => {
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
                            : `${p.label}（未配置）`
                        }
                      >
                        <span className="inline-flex min-w-0 flex-1 items-center gap-1.5">
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-(--paper)">
                            <Image
                              src={
                                providerLogoMap[p.provider] ||
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
                              : "就绪"
                            : "未配置"}
                        </span>
                      </button>
                      {p.enabled && (
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
        <div className="chat-scroll">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-hero">
                <h1 className="empty-hero-title">探索你的收藏</h1>
                <p className="empty-hero-copy">
                  基于当前提问范围回答，可切换整个知识库、收藏夹或单个视频。
                </p>
              </div>
              <div className="prompt-grid">
                {[
                  "总结收藏夹里最有价值的内容",
                  "有哪些适合快速复习的系列？",
                  "列出与某个主题相关的视频并给出关键点",
                  "按主题整理我的收藏夹内容",
                  "用一句话概括每个视频的重点",
                  "推荐3个最适合入门的学习视频",
                ].map((q, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(q)}
                    className="prompt-chip"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-window">
              {messages.map((m, idx) => (
                <div key={m.id} className={`message ${m.role}`}>
                  <div className="message-main">
                    <div
                      className={`message-bubble ${m.role === "user" && editingMessageId === m.id ? "editing" : ""}`}
                    >
                      {m.role === "assistant" && m.thinkingStartedAt && (
                        <ThinkingProcess
                          key={m.thinkingStartedAt}
                          active={Boolean(m.thinkingActive)}
                          startedAt={m.thinkingStartedAt}
                          durationMs={m.thinkingDurationMs}
                          thinking={m.thinking}
                        />
                      )}
                      {m.role === "assistant" && m.webSearchActive && (
                        <div
                          className="web-search-live-status"
                          role="status"
                          aria-live="polite"
                        >
                          <span className="web-search-live-dot" />
                          <span className="web-search-live-text">
                            {m.webSearchProgress || "正在联网搜索外部资料"}
                          </span>
                        </div>
                      )}
                      {m.role === "user" && editingMessageId === m.id ? (
                        <div className="inline-edit-wrap">
                          <textarea
                            value={editingQuestion}
                            onChange={(e) => setEditingQuestion(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                void handleSubmitEditedQuestion(m.id);
                              }
                            }}
                            className="inline-edit-input"
                            rows={3}
                            autoFocus
                            placeholder="修改你的问题..."
                          />
                          <div className="inline-edit-actions">
                            <button
                              type="button"
                              className="inline-edit-btn ghost"
                              onClick={handleCancelEdit}
                            >
                              取消
                            </button>
                            <button
                              type="button"
                              className="inline-edit-btn primary"
                              onClick={() =>
                                void handleSubmitEditedQuestion(m.id)
                              }
                              disabled={!editingQuestion.trim()}
                            >
                              发送
                            </button>
                          </div>
                        </div>
                      ) : (
                        <ReactMarkdown
                          className="markdown"
                          remarkPlugins={[remarkGfm]}
                          components={{
                            pre: ({ children }) => <>{children}</>,
                            code: ({ className, children, ...props }) => (
                              <MarkdownCode
                                inline={!className?.startsWith("language-")}
                                className={className}
                                {...props}
                              >
                                {children}
                              </MarkdownCode>
                            ),
                          }}
                        >
                          {m.content}
                        </ReactMarkdown>
                      )}
                      {((m.sources && m.sources.length > 0) || m.webSearch) && (
                        <details className="source-details">
                          <summary className="source-summary">
                            {(m.sources?.length ?? 0) > 0
                              ? `参考链接（${m.sources?.length ?? 0}）`
                              : "搜索状态"}
                          </summary>
                          <div className="source-list">
                            {m.sources?.map((s, i) => (
                              <a
                                key={i}
                                href={s.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="source-link"
                              >
                                <span className="source-type-badge">
                                  {s.type === "web" ? "网页" : "知识库"}
                                </span>
                                <span className="source-link-title">
                                  {s.title}
                                </span>
                              </a>
                            ))}
                            {m.webSearch?.message && (
                              <div className="web-search-block">
                                <div
                                  className={`web-search-status ${m.webSearch.status}`}
                                >
                                  {m.webSearch.message}
                                </div>
                                {(!m.webSearch.results ||
                                  m.webSearch.results.length === 0) &&
                                  m.webSearch.queries &&
                                  m.webSearch.queries.length > 0 && (
                                    <div className="web-search-details">
                                      <div className="web-search-detail-label">
                                        尝试查询
                                      </div>
                                      <div className="web-search-query-list">
                                        {m.webSearch.queries.map((query) => (
                                          <span
                                            key={query}
                                            className="web-search-query"
                                          >
                                            {query}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                {m.webSearch.errors &&
                                  m.webSearch.errors.length > 0 && (
                                    <div className="web-search-details">
                                      <div className="web-search-detail-label">
                                        诊断信息
                                      </div>
                                      <div className="web-search-error-list">
                                        {m.webSearch.errors.map(
                                          (error, index) => (
                                            <span
                                              key={`${error.source || "web"}-${error.query || error.url || index}-${index}`}
                                              className="web-search-error"
                                            >
                                              {error.message}
                                            </span>
                                          ),
                                        )}
                                      </div>
                                    </div>
                                  )}
                              </div>
                            )}
                          </div>
                        </details>
                      )}
                      {m.role === "assistant" && m.content.trim() && (
                        <div
                          className="message-actions"
                          role="group"
                          aria-label="回答操作"
                        >
                          <button
                            type="button"
                            className={`message-action-btn ${copiedMessageId === m.id ? "active" : ""}`}
                            title="复制"
                            aria-label="复制"
                            onClick={() =>
                              void handleCopyMessage(m.id, m.content)
                            }
                          >
                            {copiedMessageId === m.id ? (
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                            ) : (
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <rect
                                  x="9"
                                  y="9"
                                  width="13"
                                  height="13"
                                  rx="2"
                                  ry="2"
                                  strokeWidth={1.8}
                                />
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={1.8}
                                  d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                                />
                              </svg>
                            )}
                          </button>
                          <button
                            type="button"
                            className={`message-action-btn soft-active ${regeneratingMessageId === m.id ? "active spinning" : ""}`}
                            title="重新生成"
                            aria-label="重新生成"
                            disabled={!!regeneratingMessageId}
                            onClick={() => {
                              let question = "";
                              for (let i = idx - 1; i >= 0; i -= 1) {
                                if (messages[i].role === "user") {
                                  question = messages[i].content;
                                  break;
                                }
                              }
                              void handleRegenerate(m.id, question);
                            }}
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.9}
                                d="M21 12a9 9 0 11-2.2-5.9l1.7 1.9h-3.1"
                              />
                            </svg>
                          </button>
                          <button
                            type="button"
                            className={`message-action-btn soft-active ${reactionMap[m.id] === "like" ? "active" : ""}`}
                            title="点赞"
                            aria-label="点赞"
                            onClick={() => handleReaction(m.id, "like")}
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M14 9V5a3 3 0 0 0-3-3l-1 5-3 3v9h11a3 3 0 0 0 3-3v-5a2 2 0 0 0-2-2h-5z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M7 10H4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h3z"
                              />
                            </svg>
                          </button>
                          <button
                            type="button"
                            className={`message-action-btn ${reactionMap[m.id] === "dislike" ? "active" : ""}`}
                            title="点踩"
                            aria-label="点踩"
                            onClick={() => handleReaction(m.id, "dislike")}
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.9}
                                d="M10 15v4a3 3 0 0 0 3 3l1-5 3-3V5H6a3 3 0 0 0-3 3v5a2 2 0 0 0 2 2h5z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.9}
                                d="M17 14h3a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                      )}
                    </div>
                    {m.role === "user" &&
                      m.content.trim() &&
                      editingMessageId !== m.id && (
                        <div
                          className="message-actions user-message-actions"
                          role="group"
                          aria-label="问题操作"
                        >
                          <button
                            type="button"
                            className={`message-action-btn ${copiedMessageId === m.id ? "active" : ""}`}
                            title="复制问题"
                            aria-label="复制问题"
                            onClick={() =>
                              void handleCopyMessage(m.id, m.content)
                            }
                          >
                            {copiedMessageId === m.id ? (
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                            ) : (
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <rect
                                  x="9"
                                  y="9"
                                  width="13"
                                  height="13"
                                  rx="2"
                                  ry="2"
                                  strokeWidth={1.8}
                                />
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={1.8}
                                  d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                                />
                              </svg>
                            )}
                          </button>
                          <button
                            type="button"
                            className="message-action-btn"
                            title="更改问题"
                            aria-label="更改问题"
                            onClick={() => handleEditQuestion(m.id, m.content)}
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M15.232 5.232l3.536 3.536M9 11l6.768-6.768a2.5 2.5 0 013.536 0l.232.232a2.5 2.5 0 010 3.536L12.768 14.768A2 2 0 0111.354 15H9v-2.354A2 2 0 019.586 11.939zM5 19h14"
                              />
                            </svg>
                          </button>
                        </div>
                      )}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
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
          <div className="relative composer-shell">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => handleComposerChange(e.target.value, e.target)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void (isGenerating ? stopGenerating() : send());
                }
              }}
              placeholder={
                knowledgeBaseId ? "输入问题..." : "请先选择或创建知识库"
              }
              className="input composer-input w-full shadow-sm"
              rows={1}
              disabled={!knowledgeBaseId}
            />
            <div className="composer-mode-row">
              <ChatScopePicker
                options={scopeOptions}
                value={chatScope}
                webSearchEnabled={webSearchEnabled}
                webSearchProvider={webSearchProvider}
                tavilyConfigured={Boolean(webSearchConfig?.tavily_configured)}
                webSearchNotice={webSearchNotice}
                onChange={handleScopeChange}
                onWebSearchChange={handleWebSearchChange}
                onWebSearchProviderChange={handleWebSearchProviderChange}
                onConfigureTavily={openWebSearchConfig}
                disabled={!knowledgeBaseId}
              />
              <button
                onClick={isGenerating ? stopGenerating : send}
                disabled={!canSend && !isGenerating}
                className={`composer-send-button ${canSend || isGenerating ? "active" : "disabled"} ${isGenerating ? "generating" : ""}`}
                title={isGenerating ? "停止生成" : "发送"}
                aria-label={isGenerating ? "停止生成" : "发送"}
                type="button"
              >
                {isGenerating ? (
                  <svg
                    className="send-stop-icon"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <rect x="6" y="6" width="12" height="12" rx="2.4" />
                  </svg>
                ) : (
                  <>
                    <svg
                      className="send-arrow-icon"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.35}
                        d="M12 19V5m0 0-6 6m6-6 6 6"
                      />
                    </svg>
                    发送
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
        <div className="composer-disclaimer text-[10px] text-(--muted) text-center">
          内容由 AI 生成，请注意甄别。
        </div>
      </div>

      {webSearchConfigOpen && (
        <div
          className="modal-backdrop"
          onMouseDown={() => closeWebSearchConfig()}
        >
          <div
            className="modal-card thinking-provider-modal"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="provider-config-head">
              <div className="provider-config-title-block">
                <h3 className="provider-config-title">配置联网搜索</h3>
                <p className="provider-config-subtitle">
                  Tavily API Key 会写入后端 .env.local，前端只保存是否已配置。
                </p>
              </div>
              <button
                type="button"
                className="provider-config-close"
                onClick={() => closeWebSearchConfig()}
                disabled={webSearchConfigSaving}
                aria-label="关闭联网搜索配置"
              >
                x
              </button>
            </div>

            <div className="provider-config-body">
              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                Tavily API Key
                <input
                  type="password"
                  value={webSearchApiKey}
                  onChange={(e) => setWebSearchApiKey(e.target.value)}
                  className="input provider-config-input text-center"
                  placeholder={
                    webSearchConfig?.tavily_configured
                      ? "留空沿用已保存的 Tavily API Key"
                      : "粘贴 Tavily API Key"
                  }
                  autoFocus
                />
              </label>

              {webSearchConfigError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {webSearchConfigError}
                </div>
              )}
            </div>

            <div className="provider-config-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => closeWebSearchConfig()}
                disabled={webSearchConfigSaving}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleSaveWebSearchConfig()}
                disabled={webSearchConfigSaving}
              >
                {webSearchConfigSaving ? "保存中..." : "保存配置"}
              </button>
            </div>
          </div>
        </div>
      )}

      {configProvider && (
        <div
          className="modal-backdrop"
          onMouseDown={() => closeProviderConfig()}
        >
          <div
            className="modal-card thinking-provider-modal"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="provider-config-head">
              <div className="provider-config-title-block">
                <h3 className="provider-config-title">
                  配置 {configProvider.label}
                </h3>
                <p className="provider-config-subtitle">
                  保存后会写入项目的 .env.local，并自动切换到该模型。
                </p>
              </div>
              <button
                type="button"
                className="provider-config-close"
                onClick={() => closeProviderConfig()}
                disabled={configSaving}
                aria-label="关闭配置弹窗"
              >
                ×
              </button>
            </div>

            <div className="provider-config-body">
              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                API Key
                <input
                  type="password"
                  value={configApiKey}
                  onChange={(e) => setConfigApiKey(e.target.value)}
                  className="input provider-config-input text-center"
                  placeholder={
                    configProvider.enabled
                      ? "留空沿用已保存的 API Key"
                      : "粘贴对应平台的 API Key"
                  }
                  autoFocus
                />
              </label>

              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                Base URL
                <input
                  type="text"
                  value={configBaseUrl}
                  onChange={(e) => setConfigBaseUrl(e.target.value)}
                  className="input provider-config-input"
                  placeholder="留空使用默认地址"
                />
              </label>

              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                模型名称
                <input
                  type="text"
                  value={configModel}
                  onChange={(e) => setConfigModel(e.target.value)}
                  className="input provider-config-input"
                  placeholder={configProvider.model}
                />
              </label>

              <fieldset className="thinking-config-fieldset">
                <legend>思考配置</legend>
                <div className="thinking-mode-options">
                  {(
                    [
                      ["off", "关闭"],
                      ["standard", "标准模板"],
                      ["custom", "自定义 JSON"],
                    ] as const
                  ).map(([mode, label]) => (
                    <button
                      key={mode}
                      type="button"
                      className={`thinking-mode-option ${
                        configThinkingMode === mode ? "active" : ""
                      }`}
                      onClick={() => {
                        setConfigThinkingMode(mode);
                        if (mode === "off") {
                          setConfigThinkingJson("{}");
                        } else if (mode === "standard") {
                          setConfigThinkingJson(
                            formatThinkingConfig(
                              configProvider.thinking_template || {},
                            ),
                          );
                        } else if (configThinkingJson === "{}") {
                          setConfigThinkingJson(
                            formatThinkingConfig(
                              configProvider.thinking_template || {},
                            ),
                          );
                        }
                        setConfigError("");
                      }}
                      disabled={
                        mode === "standard" &&
                        Object.keys(configProvider.thinking_template || {})
                          .length === 0
                      }
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {configThinkingMode !== "off" && (
                  <label className="thinking-json-editor">
                    <span>
                      请求体 JSON
                      {configThinkingMode === "standard" && "（标准模板）"}
                    </span>
                    <textarea
                      value={configThinkingJson}
                      onChange={(event) =>
                        setConfigThinkingJson(event.target.value)
                      }
                      readOnly={configThinkingMode === "standard"}
                      spellCheck={false}
                      rows={7}
                      wrap="soft"
                    />
                  </label>
                )}
                <p className="thinking-config-help">
                  保存时会发送最小测试请求。验证成功后才写入
                  .env.local，并自动应用到后续对话。
                </p>
              </fieldset>

              {configError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {configError}
                </div>
              )}
            </div>

            <div className="provider-config-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => closeProviderConfig()}
                disabled={configSaving}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleSaveProviderConfig()}
                disabled={configSaving}
              >
                {configSaving ? "保存中..." : "保存配置"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
