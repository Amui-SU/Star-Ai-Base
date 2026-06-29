"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  chatApi,
  type WebSearchConfigResponse,
  type WebSearchProvider,
} from "@/lib/api";

interface UseChatWebSearchSettingsOptions {
  apiAccountsKey: number;
  isAdmin: boolean;
  onOpenApiAccounts?: () => void;
  onScopeNotice: (message: string) => void;
}

export function useChatWebSearchSettings({
  apiAccountsKey,
  isAdmin,
  onOpenApiAccounts,
  onScopeNotice,
}: UseChatWebSearchSettingsOptions) {
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [webSearchProvider, setWebSearchProvider] =
    useState<WebSearchProvider>("auto");
  const [webSearchConfig, setWebSearchConfig] =
    useState<WebSearchConfigResponse | null>(null);
  const [webSearchConfigOpen, setWebSearchConfigOpen] = useState(false);
  const [webSearchApiKey, setWebSearchApiKey] = useState("");
  const [webSearchConfigSaving, setWebSearchConfigSaving] = useState(false);
  const [webSearchConfigError, setWebSearchConfigError] = useState("");
  const [webSearchNotice, setWebSearchNotice] = useState("");
  const webSearchNoticeTimerRef = useRef<number | null>(null);

  const clearWebSearchNotice = useCallback(() => {
    if (webSearchNoticeTimerRef.current) {
      window.clearTimeout(webSearchNoticeTimerRef.current);
      webSearchNoticeTimerRef.current = null;
    }
    setWebSearchNotice("");
  }, []);

  const showWebSearchNotice = useCallback(
    (message: string, timeoutMs?: number) => {
      if (webSearchNoticeTimerRef.current) {
        window.clearTimeout(webSearchNoticeTimerRef.current);
        webSearchNoticeTimerRef.current = null;
      }
      setWebSearchNotice(message);
      if (timeoutMs !== undefined) {
        webSearchNoticeTimerRef.current = window.setTimeout(() => {
          setWebSearchNotice("");
          webSearchNoticeTimerRef.current = null;
        }, timeoutMs);
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.resolve(chatApi.getWebSearchConfig())
      .then((webCfg) => {
        if (!webCfg) return;
        if (!cancelled) {
          setWebSearchConfig(webCfg);
          setWebSearchProvider(webCfg.provider || "auto");
        }
      })
      .catch(() => {
        // 忽略联网搜索配置加载失败，不影响聊天主流程
      });
    return () => {
      cancelled = true;
    };
  }, [apiAccountsKey]);

  useEffect(() => {
    return () => {
      if (webSearchNoticeTimerRef.current) {
        window.clearTimeout(webSearchNoticeTimerRef.current);
      }
    };
  }, []);

  const openWebSearchConfig = useCallback(() => {
    if (onOpenApiAccounts) {
      setWebSearchConfigError("");
      showWebSearchNotice("请在 AI 服务密钥中添加 Tavily");
      onOpenApiAccounts();
      return;
    }
    if (!isAdmin) {
      setWebSearchConfigError("");
      showWebSearchNotice("Tavily 需要管理员配置");
      return;
    }
    setWebSearchApiKey("");
    setWebSearchConfigError("");
    setWebSearchConfigOpen(true);
  }, [isAdmin, onOpenApiAccounts, showWebSearchNotice]);

  const closeWebSearchConfig = useCallback(
    (force = false) => {
      if (webSearchConfigSaving && !force) return;
      setWebSearchConfigOpen(false);
      setWebSearchApiKey("");
      setWebSearchConfigError("");
    },
    [webSearchConfigSaving],
  );

  const handleSaveWebSearchConfig = useCallback(async () => {
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
      showWebSearchNotice("联网搜索已开启");
      closeWebSearchConfig(true);
    } catch (err) {
      setWebSearchConfigError(
        err instanceof Error ? err.message : "保存联网搜索配置失败",
      );
    } finally {
      setWebSearchConfigSaving(false);
    }
  }, [
    closeWebSearchConfig,
    showWebSearchNotice,
    webSearchApiKey,
    webSearchConfig,
    webSearchConfigSaving,
  ]);

  const handleWebSearchChange = useCallback(
    (enabled: boolean) => {
      const notice = enabled ? "联网搜索已开启" : "联网搜索已关闭";
      setWebSearchEnabled(enabled);
      if (enabled) {
        setWebSearchProvider("auto");
      }
      showWebSearchNotice(notice, 2200);
      onScopeNotice("");
    },
    [onScopeNotice, showWebSearchNotice],
  );

  const handleWebSearchProviderChange = useCallback(
    (provider: WebSearchProvider) => {
      if (
        provider === "tavily" &&
        !webSearchConfig?.tavily_configured &&
        !isAdmin &&
        !onOpenApiAccounts
      ) {
        showWebSearchNotice("Tavily 需要管理员配置");
        return;
      }
      setWebSearchProvider(provider);
      setWebSearchEnabled(true);
      if (provider === "tavily" && !webSearchConfig?.tavily_configured) {
        showWebSearchNotice("请先添加 Tavily 服务密钥");
        openWebSearchConfig();
      }
    },
    [
      isAdmin,
      onOpenApiAccounts,
      openWebSearchConfig,
      showWebSearchNotice,
      webSearchConfig?.tavily_configured,
    ],
  );

  return {
    clearWebSearchNotice,
    closeWebSearchConfig,
    handleSaveWebSearchConfig,
    handleWebSearchChange,
    handleWebSearchProviderChange,
    openWebSearchConfig,
    setWebSearchEnabled,
    setWebSearchProvider,
    webSearchApiKey,
    webSearchConfig,
    webSearchConfigError,
    webSearchConfigOpen,
    webSearchConfigSaving,
    webSearchEnabled,
    webSearchNotice,
    webSearchProvider,
    setWebSearchApiKey,
  };
}
