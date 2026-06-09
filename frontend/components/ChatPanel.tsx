"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Image from "next/image";
import {
  chatApi,
  knowledgeBaseApi,
  KnowledgeStats,
  LLMHealthResponse,
  LLMConfigResponse,
  LLMProvider,
} from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: Array<{ bvid: string; title: string; url: string }>;
}
type Reaction = "like" | "dislike" | null;

interface Props {
  statsKey?: number;
  folderIds?: number[];
  sidebarOpen?: boolean;
  knowledgeBaseId?: number | null;
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
  folderIds,
  sidebarOpen = true,
  knowledgeBaseId,
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
  const [smartSearchEnabled, setSmartSearchEnabled] = useState(false);
  const [deepThinkEnabled, setDeepThinkEnabled] = useState(false);
  const [thinkingExpandedMap, setThinkingExpandedMap] = useState<
    Record<string, boolean>
  >({});
  const [reactionMap, setReactionMap] = useState<Record<string, Reaction>>({});
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
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
  } | null>(null);
  const [configApiKey, setConfigApiKey] = useState("");
  const [configBaseUrl, setConfigBaseUrl] = useState("");
  const [configModel, setConfigModel] = useState("");
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const sourcesMarker = "[[SOURCES_JSON]]";
  const thinkingMarker = "[[THINKING_JSON]]";
  const THINKING_PREVIEW_LIMIT = 220;
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
  }) => {
    setConfigProvider(provider);
    setConfigApiKey("");
    setConfigBaseUrl(provider.base_url || "");
    setConfigModel(provider.model || "");
    setConfigError("");
    setModelMenuOpen(false);
  };

  const closeProviderConfig = (force = false) => {
    if (configSaving && !force) return;
    setConfigProvider(null);
    setConfigApiKey("");
    setConfigBaseUrl("");
    setConfigModel("");
    setConfigError("");
  };

  const handleSaveProviderConfig = async () => {
    if (!configProvider || configSaving) return;
    if (!configApiKey.trim()) {
      setConfigError("请填写 API Key");
      return;
    }
    setConfigSaving(true);
    setConfigError("");
    try {
      await chatApi.saveModelProviderConfig({
        provider: configProvider.provider,
        api_key: configApiKey.trim(),
        base_url: configBaseUrl.trim() || undefined,
        model: configModel.trim() || undefined,
      });
      const [cfg, health] = await Promise.all([
        chatApi.getModelConfig(),
        chatApi.health(),
      ]);
      setLlmConfig(cfg);
      setLlmHealth(health);
      closeProviderConfig(true);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setConfigSaving(false);
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
        const cfg = await chatApi.getModelConfig();
        if (!cancelled) setLlmConfig(cfg);
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
    endRef.current?.scrollIntoView({ behavior: "smooth" });
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
    let streamTimedOut = false;
    const streamTimeout = window.setTimeout(() => {
      streamTimedOut = true;
      abortController.abort();
    }, 45000);
    try {
      if (!knowledgeBaseId) return;
      const streamUrl = knowledgeBaseApi.chatStreamUrl(knowledgeBaseId);
      const streamBody = JSON.stringify({
        question: q,
        k: 5,
        smart_search: smartSearchEnabled,
        deep_think: deepThinkEnabled,
      });
      const response = await fetch(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: streamBody,
      });

      if (!response.ok || !response.body) {
        throw new Error("流式接口不可用");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      let buffer = "";

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          if (chunk) {
            buffer += chunk;
            const markerIndexes = [
              buffer.indexOf(thinkingMarker),
              buffer.indexOf(sourcesMarker),
            ].filter((idx) => idx >= 0);
            const firstMarkerIndex =
              markerIndexes.length > 0 ? Math.min(...markerIndexes) : -1;
            const visibleText =
              firstMarkerIndex >= 0
                ? buffer.slice(0, firstMarkerIndex)
                : buffer;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: visibleText } : m,
              ),
            );
          }
        }
      }

      const extractMarkerJson = (
        fullText: string,
        marker: string,
        nextMarker?: string,
      ) => {
        const start = fullText.indexOf(marker);
        if (start < 0) return "";
        const from = start + marker.length;
        if (!nextMarker) return fullText.slice(from).trim();
        const next = fullText.indexOf(nextMarker, from);
        if (next < 0) return fullText.slice(from).trim();
        return fullText.slice(from, next).trim();
      };

      const thinkingJson = extractMarkerJson(
        buffer,
        thinkingMarker,
        sourcesMarker,
      );
      const sourcesJson = extractMarkerJson(buffer, sourcesMarker);
      const contentEndIndexes = [
        buffer.indexOf(thinkingMarker),
        buffer.indexOf(sourcesMarker),
      ].filter((idx) => idx >= 0);
      const contentEnd =
        contentEndIndexes.length > 0
          ? Math.min(...contentEndIndexes)
          : buffer.length;
      const finalContent = buffer.slice(0, contentEnd);

      let parsedThinking = "";
      if (thinkingJson) {
        try {
          parsedThinking = JSON.parse(thinkingJson);
        } catch {
          parsedThinking = "";
        }
      }

      let parsedSources: Array<{ bvid: string; title: string; url: string }> =
        [];
      if (sourcesJson) {
        try {
          const parsed = JSON.parse(sourcesJson);
          if (Array.isArray(parsed)) parsedSources = parsed;
        } catch {
          parsedSources = [];
        }
      }

      const extracted = extractThinkingFromContent(finalContent);
      const finalThinking = (parsedThinking || extracted.thinking || "").trim();
      const finalAnswer = parsedThinking
        ? finalContent.trim() ||
          (finalThinking ? "（已生成思考过程，展开查看）" : "")
        : extracted.answer;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: finalAnswer,
                thinking: finalThinking || undefined,
                sources: parsedSources,
              }
            : m,
        ),
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        if (!streamTimedOut) {
          return;
        }
      }
      try {
        if (!knowledgeBaseId) return;
        const res = await knowledgeBaseApi.chat(knowledgeBaseId, {
          question: q,
          k: 5,
          smart_search: smartSearchEnabled,
          deep_think: deepThinkEnabled,
        });
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
                  sources: res.sources,
                }
              : m,
          ),
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `错误: ${err instanceof Error ? err.message : "请求失败"}`,
                }
              : m,
          ),
        );
      }
    } finally {
      window.clearTimeout(streamTimeout);
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
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 74), 220);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > 220 ? "auto" : "hidden";
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
        m.id === assistantId ? { ...m, content: "", sources: [] } : m,
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

  useEffect(() => {
    adjustComposerHeight();
  }, [input]);

  return (
    <div className="panel-inner">
      {/* 聊天区域外顶部工具栏：同一行，向中部靠拢 */}
      <div
        className={`fixed top-4 z-40 w-[calc(100vw-160px)] max-w-[960px] flex items-center justify-between ${
          sidebarOpen
            ? "left-1/2 -translate-x-1/2"
            : "left-[calc(50%-220px)] -translate-x-1/2"
        }`}
      >
        <div className="flex flex-col items-start gap-1.5">
          <div className="inline-flex items-center gap-0 rounded-full border border-(--border) bg-(--paper-2) p-0.5 shadow-sm">
            <span
              className={`status-pill ${llmChecking ? "empty" : llmHealth?.status === "ok" ? "ok" : "alert"} px-1.5 py-0.5 text-[10px]`}
              title={llmHealth?.message || "模型状态检查中"}
            >
              {llmChecking
                ? "模型检查中"
                : llmHealth?.status === "ok"
                  ? `${llmHealth.latency_ms != null ? `${llmHealth.latency_ms}ms` : "-- ms"}`
                  : "模型异常"}
            </span>
            <span className="mx-1 h-4 w-px bg-(--border)" aria-hidden="true" />
            <div className="relative" ref={modelMenuRef}>
              <button
                type="button"
                disabled={llmSwitching}
                onClick={() => setModelMenuOpen((v) => !v)}
                className="inline-flex items-center gap-1 rounded-full bg-transparent hover:bg-(--paper-3) h-[26px] px-2 transition disabled:opacity-50"
                title={
                  activeProvider
                    ? `${activeProvider.label} · ${activeProvider.model}`
                    : "模型选择"
                }
                aria-label="模型选择"
              >
                {activeProvider && (
                  <>
                    <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-sm">
                      <Image
                        src={
                          providerLogoMap[activeProvider.provider] ||
                          "/logos/qwen-icon.png"
                        }
                        alt={`${activeProvider.label} logo`}
                        width={12}
                        height={12}
                        unoptimized
                        className="rounded-sm object-contain"
                      />
                    </span>
                    <span className="text-[10px] text-(--ink-soft) leading-none max-w-[96px] truncate">
                      {activeProvider.label}
                    </span>
                    <svg
                      className="w-2.5 h-2.5 text-(--muted)"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </>
                )}
              </button>

              {modelMenuOpen && (
                <div className="absolute top-[34px] left-1/2 -translate-x-1/2 z-20 w-[198px] max-w-[calc(100vw-32px)] rounded-xl border border-(--border) bg-(--paper-2) shadow-xl p-2 flex flex-col gap-2.5 backdrop-blur-sm">
                  {providersForMenu.map((p) => (
                    <button
                      key={p.provider}
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
                      className={`w-full inline-flex items-center min-h-[44px] rounded-lg px-1.5 py-2.5 text-left overflow-hidden transition ${
                        p.provider === currentProvider
                          ? "bg-(--paper-3) text-(--ink-soft) ring-1 ring-[rgba(95,163,255,0.55)] shadow-[inset_0_0_0_1px_rgba(95,163,255,0.18)]"
                          : "text-(--muted) hover:bg-(--paper-3)"
                      } disabled:opacity-45`}
                      title={
                        p.enabled
                          ? `${p.label} · ${p.model}`
                          : `${p.label}（未配置）`
                      }
                    >
                      <span className="inline-flex min-w-0 flex-1 items-center gap-1.5 translate-x-4">
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
                      <span className="inline-flex shrink-0 items-center gap-1 -translate-x-4">
                        {p.enabled ? (
                          <span className="whitespace-nowrap text-[8px] px-1 py-0.5 rounded-full bg-[rgba(47,124,120,0.12)] text-[#1f7a75] border border-[rgba(47,124,120,0.28)]">
                            就绪
                          </span>
                        ) : (
                          <span className="whitespace-nowrap text-[8px] px-1 py-0.5 rounded-full bg-(--paper) text-(--accent-strong) border border-[rgba(217,139,43,0.35)]">
                            未配置
                          </span>
                        )}
                        {p.provider === currentProvider && p.enabled && (
                          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-[rgba(95,163,255,0.18)] text-(--accent-strong) text-[10px]">
                            ✓
                          </span>
                        )}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {stats && (stats.total_videos ?? 0) > 0 && (
            <span className="block relative left-4 text-[11px] text-(--muted) leading-none">
              已收录 {stats.total_videos} 个视频
            </span>
          )}
        </div>
      </div>

      {messages.length > 0 && (
        <div className="fixed top-4 right-[120px] z-40">
          <button
            onClick={() => setMessages([])}
            className="btn btn-ghost"
            title="清空"
          >
            清空对话
          </button>
        </div>
      )}

      <div className="panel-body">
        <div className="chat-scroll">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div>
                <div className="status-pill">检索就绪</div>
                <p className="text-sm text-(--muted) mt-3">
                  把收藏夹变成可提问的知识库
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
                      {m.role === "assistant" &&
                        m.thinking &&
                        m.thinking.trim() && (
                          <div className="thinking-block">
                            <div className="thinking-header">思考过程</div>
                            <div className="thinking-content">
                              {thinkingExpandedMap[m.id] ||
                              m.thinking.length <= THINKING_PREVIEW_LIMIT
                                ? m.thinking
                                : `${m.thinking.slice(0, THINKING_PREVIEW_LIMIT)}...`}
                            </div>
                            {m.thinking.length > THINKING_PREVIEW_LIMIT && (
                              <button
                                type="button"
                                className="thinking-toggle"
                                onClick={() =>
                                  setThinkingExpandedMap((prev) => ({
                                    ...prev,
                                    [m.id]: !prev[m.id],
                                  }))
                                }
                              >
                                {thinkingExpandedMap[m.id] ? "收起" : "展开"}
                              </button>
                            )}
                          </div>
                        )}
                      {m.sources && m.sources.length > 0 && (
                        <details className="source-details">
                          <summary className="source-summary">
                            参考链接（{m.sources.length}）
                          </summary>
                          <div className="source-list">
                            {m.sources.map((s, i) => (
                              <a
                                key={i}
                                href={s.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="source-link"
                              >
                                {s.title}
                              </a>
                            ))}
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
              {loading && (
                <div className="message assistant">
                  <div className="message-bubble">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <div
                          key={i}
                          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-pulse"
                          style={{ animationDelay: `${i * 0.15}s` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      <div className="panel-footer border-transparent bg-transparent flex flex-col items-center gap-2">
        <div className="w-full max-w-3xl mx-auto mt-1">
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
              <div className="composer-chip-group">
                <button
                  type="button"
                  className={`mode-chip ${deepThinkEnabled ? "active" : ""}`}
                  onClick={() => setDeepThinkEnabled((v) => !v)}
                  title="启用深度思考模式"
                >
                  <span className="mode-chip-check" aria-hidden="true">
                    {deepThinkEnabled ? "✓" : ""}
                  </span>
                  思考
                </button>
                <button
                  type="button"
                  className={`mode-chip ${smartSearchEnabled ? "active" : ""}`}
                  onClick={() => setSmartSearchEnabled((v) => !v)}
                  title="启用智能搜索模式（模型支持时联网）"
                >
                  <span className="mode-chip-check" aria-hidden="true">
                    {smartSearchEnabled ? "✓" : ""}
                  </span>
                  联网
                </button>
              </div>
              <button
                onClick={isGenerating ? stopGenerating : send}
                disabled={!canSend && !isGenerating}
                className={`mode-chip mode-chip-send ${canSend || isGenerating ? "active" : "disabled"} ${isGenerating ? "generating" : ""}`}
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
                        strokeWidth={2}
                        d="M3 11.5L20 4l-5 16-3.5-6L3 11.5z"
                      />
                    </svg>
                    发送
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
        <div className="text-[10px] text-(--muted) text-center">
          内容由 AI 生成，请注意甄别。
        </div>
      </div>

      {configProvider && (
        <div
          className="modal-backdrop z-80"
          onMouseDown={() => closeProviderConfig()}
        >
          <div
            className="modal-card w-[min(540px,94vw)] p-8"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h3 className="modal-title text-left">
                  配置 {configProvider.label}
                </h3>
                <p className="modal-subtitle text-left whitespace-nowrap">
                  保存后会写入项目的 .env.local，并自动切换到该模型。
                </p>
              </div>
              <button
                type="button"
                className="btn btn-ghost px-2 py-1 text-xs"
                onClick={() => closeProviderConfig()}
                disabled={configSaving}
                aria-label="关闭配置弹窗"
              >
                ×
              </button>
            </div>

            <div className="mt-6 flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                API Key
                <input
                  type="password"
                  value={configApiKey}
                  onChange={(e) => setConfigApiKey(e.target.value)}
                  className="input w-full h-14 rounded-2xl border-2 px-5 text-center text-base"
                  placeholder="粘贴对应平台的 API Key"
                  autoFocus
                />
              </label>

              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                Base URL
                <input
                  type="text"
                  value={configBaseUrl}
                  onChange={(e) => setConfigBaseUrl(e.target.value)}
                  className="input w-full h-14 rounded-2xl border-2 px-5 text-base"
                  placeholder="留空使用默认地址"
                />
              </label>

              <label className="flex flex-col gap-2 text-xs font-medium text-(--ink-soft)">
                模型名称
                <input
                  type="text"
                  value={configModel}
                  onChange={(e) => setConfigModel(e.target.value)}
                  className="input w-full h-14 rounded-2xl border-2 px-5 text-base"
                  placeholder={configProvider.model}
                />
              </label>

              {configError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {configError}
                </div>
              )}

              <div className="mt-2 flex justify-end gap-2">
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
        </div>
      )}
    </div>
  );
}
