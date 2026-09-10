"use client";

import { useCallback, useEffect, useState } from "react";
import { sourceBindingApi, systemAuthApi } from "@/lib/api";
import type { KnowledgeBase, SystemUser } from "@/lib/api";
import { useRefreshEmit } from "@/hooks/refreshBus";

const ACTIVE_KB_STORAGE_KEY = "active_kb_id";
const BILIBILI_SESSION_STORAGE_KEYS = [
  "bili_session",
  "bili_user",
  "bili_user_face",
];

const getInitialActiveKbId = () => {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(ACTIVE_KB_STORAGE_KEY);
  return raw ? Number(raw) : null;
};

const loadActiveBindingId = async () => {
  const bindings = await sourceBindingApi.list();
  const active = bindings.find((binding) => binding.status === "active");
  return active?.id ?? null;
};

export function useHomePageShell() {
  const [systemUser, setSystemUser] = useState<SystemUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [activeBindingId, setActiveBindingId] = useState<number | null>(null);
  const [activeKbId, setActiveKbId] = useState<number | null>(
    getInitialActiveKbId,
  );
  const [activeKnowledgeBase, setActiveKnowledgeBase] =
    useState<KnowledgeBase | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showAdminUsers, setShowAdminUsers] = useState(false);
  const [showApiAccounts, setShowApiAccounts] = useState(false);
  const [knowledgeBuilding, setKnowledgeBuilding] = useState(false);
  const emitRefresh = useRefreshEmit();

  useEffect(() => {
    systemAuthApi
      .me()
      .then(async (user) => {
        setSystemUser(user);
        try {
          const activeId = await loadActiveBindingId();
          if (activeId) setActiveBindingId(activeId);
        } catch {
          /* 绑定接口失败不影响登录 */
        }
      })
      .catch(() => setSystemUser(null))
      .finally(() => setAuthChecking(false));
  }, []);

  const handleAuthSuccess = useCallback(
    (user: SystemUser) => {
      setSystemUser(user);
      emitRefresh("knowledge-bases");
    },
    [emitRefresh],
  );

  const handleBiliBound = useCallback(async () => {
    setShowImport(false);
    try {
      const activeId = await loadActiveBindingId();
      if (activeId) setActiveBindingId(activeId);
    } catch (error) {
      console.error("获取绑定列表失败:", error);
    }
  }, []);

  const handleLogout = useCallback(() => {
    systemAuthApi.logout().catch(() => {});
    setSystemUser(null);
    BILIBILI_SESSION_STORAGE_KEYS.forEach((key) =>
      localStorage.removeItem(key),
    );
    localStorage.removeItem(ACTIVE_KB_STORAGE_KEY);
    setActiveKbId(null);
    setActiveKnowledgeBase(null);
  }, []);

  const handleKnowledgeBaseSelect = useCallback((kb: KnowledgeBase | null) => {
    setActiveKnowledgeBase(kb);
    setActiveKbId(kb?.id ?? null);
    if (kb) {
      localStorage.setItem(ACTIVE_KB_STORAGE_KEY, String(kb.id));
    } else {
      localStorage.removeItem(ACTIVE_KB_STORAGE_KEY);
    }
  }, []);

  const openImport = useCallback(() => setShowImport(true), []);
  const closeImport = useCallback(() => setShowImport(false), []);
  const openAdminUsers = useCallback(() => setShowAdminUsers(true), []);
  const closeAdminUsers = useCallback(() => setShowAdminUsers(false), []);
  const openApiAccounts = useCallback(() => setShowApiAccounts(true), []);
  const closeApiAccounts = useCallback(() => setShowApiAccounts(false), []);
  const markStatsChanged = useCallback(
    () => emitRefresh("kb-stats"),
    [emitRefresh],
  );
  const markApiAccountsChanged = useCallback(
    () => emitRefresh("api-accounts"),
    [emitRefresh],
  );

  return {
    activeBindingId,
    activeKbId,
    activeKnowledgeBase,
    authChecking,
    knowledgeBuilding,
    showAdminUsers,
    showApiAccounts,
    showImport,
    systemUser,
    closeAdminUsers,
    closeApiAccounts,
    closeImport,
    handleAuthSuccess,
    handleBiliBound,
    handleKnowledgeBaseSelect,
    handleLogout,
    markApiAccountsChanged,
    markStatsChanged,
    openAdminUsers,
    openApiAccounts,
    openImport,
    setActiveKnowledgeBase,
    setKnowledgeBuilding,
    setSystemUser,
  };
}
