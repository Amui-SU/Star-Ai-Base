"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
} from "react";

import {
  knowledgeBaseApi,
  type KnowledgeScopeOptions,
  type KnowledgeStats,
} from "@/lib/api";
import {
  EMPTY_CHAT_SCOPE,
  type ChatScopeSelection,
  scopeEquals,
  scopeSummary,
} from "@/lib/chatScope";

export interface ChatKnowledgeContextActions {
  onMessagesClear: () => void;
  onResetConversationIdentity: () => void;
  onResetChat: () => void;
  onStopGenerating: () => void;
  onWebSearchEnabledChange: (enabled: boolean) => void;
  onWebSearchNoticeClear: () => void;
}

interface UseChatKnowledgeContextOptions {
  actionsRef: MutableRefObject<ChatKnowledgeContextActions>;
  knowledgeBaseId?: number | null;
  statsKey?: number;
}

export function useChatKnowledgeContext({
  actionsRef,
  knowledgeBaseId,
  statsKey,
}: UseChatKnowledgeContextOptions) {
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [scopeOptions, setScopeOptions] = useState<KnowledgeScopeOptions>({
    folders: [],
  });
  const [chatScope, setChatScope] =
    useState<ChatScopeSelection>(EMPTY_CHAT_SCOPE);
  const [scopeNotice, setScopeNotice] = useState("");
  const scopeNoticeTimerRef = useRef<number | null>(null);

  const clearScopeNoticeTimer = useCallback(() => {
    if (scopeNoticeTimerRef.current) {
      window.clearTimeout(scopeNoticeTimerRef.current);
      scopeNoticeTimerRef.current = null;
    }
  }, []);

  const showScopeNotice = useCallback(
    (message: string, timeoutMs?: number) => {
      setScopeNotice(message);
      clearScopeNoticeTimer();
      if (timeoutMs !== undefined) {
        scopeNoticeTimerRef.current = window.setTimeout(() => {
          setScopeNotice("");
          scopeNoticeTimerRef.current = null;
        }, timeoutMs);
      }
    },
    [clearScopeNoticeTimer],
  );

  useEffect(() => {
    let cancelled = false;
    if (knowledgeBaseId) {
      knowledgeBaseApi
        .stats(knowledgeBaseId)
        .then((value) => {
          if (!cancelled) setStats(value);
        })
        .catch(() => {});
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- switching to no knowledge base must clear stale stats immediately.
      setStats(null);
    }
    return () => {
      cancelled = true;
    };
  }, [statsKey, knowledgeBaseId]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- knowledge-base changes intentionally reset the chat context before loading scoped options. */
    actionsRef.current.onResetChat();
    actionsRef.current.onResetConversationIdentity();
    setChatScope(EMPTY_CHAT_SCOPE);
    actionsRef.current.onWebSearchEnabledChange(false);
    actionsRef.current.onWebSearchNoticeClear();
    setScopeNotice("");
    /* eslint-enable react-hooks/set-state-in-effect */
    clearScopeNoticeTimer();
  }, [actionsRef, clearScopeNoticeTimer, knowledgeBaseId]);

  useEffect(() => {
    let cancelled = false;
    if (!knowledgeBaseId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clearing the selected knowledge base must clear its scope options.
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
  }, [statsKey, knowledgeBaseId]);

  useEffect(() => {
    return () => {
      clearScopeNoticeTimer();
    };
  }, [clearScopeNoticeTimer]);

  const handleScopeChange = useCallback(
    (next: ChatScopeSelection) => {
      if (scopeEquals(chatScope, next)) return;
      actionsRef.current.onStopGenerating();
      actionsRef.current.onMessagesClear();
      actionsRef.current.onResetConversationIdentity();
      setChatScope(next);
      actionsRef.current.onWebSearchNoticeClear();
      showScopeNotice(`提问范围已更新：${scopeSummary(next)}`, 2200);
    },
    [actionsRef, chatScope, showScopeNotice],
  );

  return {
    chatScope,
    handleScopeChange,
    scopeNotice,
    scopeOptions,
    setChatScope,
    setScopeNotice,
    showScopeNotice,
    stats,
  };
}
